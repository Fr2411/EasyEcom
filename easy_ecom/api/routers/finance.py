from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.finance import (
    CreateTransactionRequest,
    FinanceOverviewResponse,
    FinanceTransaction,
    TransactionListResponse,
    UpdateTransactionRequest,
)
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.transaction_service import TransactionContext

router = APIRouter(prefix="/finance", tags=["finance"])

FROZEN_FINANCE_DETAIL = "This finance endpoint is temporarily disabled while reporting is rebuilt on canonical ledger-backed data."


def _transaction_context(user: AuthenticatedUser) -> TransactionContext:
    return TransactionContext(user=user)


@router.get("/overview", response_model=FinanceOverviewResponse)
def finance_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> FinanceOverviewResponse:
    require_page_access(user, "Finance")
    return container.reports.get_finance_overview(user)


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions(
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type: payment or expense"),
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> TransactionListResponse:
    require_page_access(user, "Finance")
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
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> List[dict]:
    require_page_access(user, "Finance")
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=FROZEN_FINANCE_DETAIL)


@router.get("/reports", response_model=List[dict])
def list_financial_reports(
    report_type: Optional[str] = Query(None, description="Type of financial report"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> List[dict]:
    del report_type
    require_page_access(user, "Finance")
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=FROZEN_FINANCE_DETAIL)
