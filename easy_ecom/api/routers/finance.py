from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.finance import (
    CreateTransactionRequest,
    FinanceOverviewResponse,
    FinanceTransaction,
    FinanceWorkspaceResponse,
    TransactionListResponse,
    UpdateTransactionRequest,
)
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.transaction_service import TransactionContext

router = APIRouter(prefix="/finance", tags=["finance"])


def _transaction_context(user: AuthenticatedUser) -> TransactionContext:
    return TransactionContext(user=user)


@router.get("/overview", response_model=FinanceOverviewResponse)
def finance_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> FinanceOverviewResponse:
    require_page_access(user, "Finance")
    return container.reports.get_finance_overview(user)


@router.get("/workspace", response_model=FinanceWorkspaceResponse)
def finance_workspace(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> FinanceWorkspaceResponse:
    require_page_access(user, "Finance")
    context = _transaction_context(user)
    return FinanceWorkspaceResponse(
        overview=container.reports.get_finance_overview(user),
        transactions=container.transaction.get_transactions(context, limit=12, offset=0),
        receivables=container.reports.list_finance_receivables(user, limit=8),
        payables=container.reports.list_finance_payables(user, limit=8),
    )


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions(
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type: payment or expense"),
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> TransactionListResponse:
    require_page_access(user, "Finance")
    if transaction_type not in (None, "payment", "expense"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="transaction_type must be payment or expense")
    context = _transaction_context(user)
    transactions = container.transaction.get_transactions(
        context,
        limit=limit,
        offset=offset,
        transaction_type=transaction_type,
    )
    return TransactionListResponse(
        transactions=transactions,
        total=container.transaction.count_transactions(context, transaction_type=transaction_type),
        limit=limit,
        offset=offset,
    )


@router.get("/transactions/{transaction_id}", response_model=FinanceTransaction)
def get_transaction(
    transaction_id: str = Path(..., description="The ID of the transaction to retrieve"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> FinanceTransaction:
    require_page_access(user, "Finance")
    transaction = container.transaction.get_transaction(_transaction_context(user), transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID {transaction_id} not found",
        )
    return transaction


@router.post("/transactions", response_model=FinanceTransaction, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction_data: CreateTransactionRequest = Body(...),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> FinanceTransaction:
    require_page_access(user, "Finance")
    return container.transaction.create_transaction(
        _transaction_context(user),
        transaction_type=transaction_data.entry_type,
        data=transaction_data.model_dump(exclude_unset=True),
    )


@router.put("/transactions/{transaction_id}", response_model=FinanceTransaction)
def update_transaction(
    transaction_id: str = Path(..., description="The ID of the transaction to update"),
    transaction_data: UpdateTransactionRequest = Body(...),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> FinanceTransaction:
    require_page_access(user, "Finance")
    payload = transaction_data.model_dump(exclude_unset=True)
    transaction_type = payload.pop("entry_type", None)
    if not transaction_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entry_type is required for update")
    try:
        return container.transaction.update_transaction(
            _transaction_context(user),
            transaction_id=transaction_id,
            transaction_type=transaction_type,
            data=payload,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower() or "authorized" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc


@router.get("/accounts", response_model=List[dict])
def list_accounts(
    container: ServiceContainer = Depends(get_container),
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> List[dict]:
    require_page_access(user, "Finance")
    overview = container.reports.get_finance_overview(user)
    report = container.reports.get_finance_report(user)
    return [
        {
            "account_code": "cash_movement",
            "account_name": "Cash movement",
            "balance": (overview.cash_in or 0) - (overview.cash_out or 0),
            "status": "net_inflow" if (overview.cash_in or 0) >= (overview.cash_out or 0) else "net_outflow",
            "note": "Current-window cash in and cash out from payments, refunds, and paid expenses.",
        },
        {
            "account_code": "receivables",
            "account_name": "Accounts receivable",
            "balance": overview.receivables or report.receivables_total,
            "status": "open" if (overview.receivables or 0) > 0 else "clear",
            "note": "Open customer balances awaiting collection.",
        },
        {
            "account_code": "payables",
            "account_name": "Accounts payable",
            "balance": overview.payables or report.payables_total or 0,
            "status": "open" if (overview.payables or report.payables_total or 0) > 0 else "clear",
            "note": "Unpaid supplier or operating expenses in the current window.",
        },
        {
            "account_code": "sales_revenue",
            "account_name": "Sales revenue",
            "balance": overview.sales_revenue or 0,
            "status": "active",
            "note": "Confirmed sales revenue in the current operating window.",
        },
        {
            "account_code": "expenses",
            "account_name": "Expenses",
            "balance": overview.expense_total or report.expense_total,
            "status": "active",
            "note": "Operational expense total captured by the finance journal.",
        },
    ]


@router.get("/reports", response_model=List[dict])
def list_financial_reports(
    report_type: Optional[str] = Query(None, description="Type of financial report"),
    container: ServiceContainer = Depends(get_container),
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> List[dict]:
    require_page_access(user, "Finance")
    report = container.reports.get_finance_report(user)
    overview = container.reports.get_finance_overview(user)

    if report_type == "trend":
        return [
            {
                "report_code": "expense_trend",
                "title": "Expense trend",
                "items": report.expense_trend,
            },
            {
                "report_code": "cash_position",
                "title": "Cash position",
                "cash_in": overview.cash_in or 0,
                "cash_out": overview.cash_out or 0,
                "net_operating": overview.net_operating or report.net_operating_snapshot or 0,
            },
        ]

    return [
        {
            "report_code": "working_capital",
            "title": "Working capital snapshot",
            "receivables": report.receivables_total,
            "payables": report.payables_total or 0,
            "net_operating_snapshot": report.net_operating_snapshot or 0,
            "deferred_metrics": [metric.model_dump() for metric in report.deferred_metrics],
        },
        {
            "report_code": "cash_visibility",
            "title": "Cash visibility",
            "cash_in": overview.cash_in or 0,
            "cash_out": overview.cash_out or 0,
            "sales_revenue": overview.sales_revenue or 0,
            "expenses": overview.expense_total or 0,
        },
    ]
