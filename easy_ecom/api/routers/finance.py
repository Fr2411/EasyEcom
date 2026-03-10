from fastapi import APIRouter, Depends, HTTPException, Query

from easy_ecom.api.dependencies import RequestUser, ServiceContainer, get_container, get_current_user, require_page_access
from easy_ecom.api.schemas.finance import (
    ExpenseCreateRequest,
    ExpenseItem,
    ExpenseListResponse,
    ExpenseMutationResponse,
    ExpenseUpdateRequest,
    FinanceOverviewResponse,
    FinanceTransactionItem,
    FinanceTransactionsResponse,
    PayablesResponse,
    ReceivableItem,
    ReceivablesResponse,
)
from easy_ecom.domain.services.finance_api_service import ExpenseCreateInput, ExpenseUpdateInput

router = APIRouter(prefix="/finance", tags=["finance"])


def _require_service(container: ServiceContainer):
    service = getattr(container, "finance_mvp", None)
    if service is None:
        raise HTTPException(status_code=501, detail="Finance MVP API requires postgres backend")
    return service


@router.get("/overview", response_model=FinanceOverviewResponse)
def finance_overview(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> FinanceOverviewResponse:
    require_page_access(user, "Finance")
    return FinanceOverviewResponse(**_require_service(container).finance_overview(client_id=user.client_id))


@router.get("/expenses", response_model=ExpenseListResponse)
def list_expenses(
    q: str = Query(default="", max_length=100),
    payment_status: str = Query(default="", max_length=20),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ExpenseListResponse:
    require_page_access(user, "Finance")
    service = _require_service(container)
    try:
        rows = service.list_expenses(client_id=user.client_id, query=q, payment_status=payment_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExpenseListResponse(items=[ExpenseItem(**row) for row in rows])


@router.post("/expenses", response_model=ExpenseMutationResponse, status_code=201)
def create_expense(
    payload: ExpenseCreateRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ExpenseMutationResponse:
    require_page_access(user, "Finance")
    service = _require_service(container)
    try:
        row = service.create_expense(
            client_id=user.client_id,
            user_id=user.user_id,
            payload=ExpenseCreateInput(**payload.model_dump()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExpenseMutationResponse(expense=ExpenseItem(**row))


@router.patch("/expenses/{expense_id}", response_model=ExpenseMutationResponse)
def update_expense(
    expense_id: str,
    payload: ExpenseUpdateRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ExpenseMutationResponse:
    require_page_access(user, "Finance")
    service = _require_service(container)
    try:
        row = service.update_expense(
            client_id=user.client_id,
            expense_id=expense_id,
            payload=ExpenseUpdateInput(**payload.model_dump()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return ExpenseMutationResponse(expense=ExpenseItem(**row))


@router.get("/receivables", response_model=ReceivablesResponse)
def list_receivables(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ReceivablesResponse:
    require_page_access(user, "Finance")
    rows = _require_service(container).list_receivables(client_id=user.client_id)
    return ReceivablesResponse(items=[ReceivableItem(**row) for row in rows])


@router.get("/payables", response_model=PayablesResponse)
def list_payables(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> PayablesResponse:
    require_page_access(user, "Finance")
    response = _require_service(container).list_payables(client_id=user.client_id)
    response["rows"] = [ExpenseItem(**row) for row in response["rows"]]
    return PayablesResponse(**response)


@router.get("/transactions", response_model=FinanceTransactionsResponse)
def list_transactions(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> FinanceTransactionsResponse:
    require_page_access(user, "Finance")
    rows = _require_service(container).list_transactions(client_id=user.client_id)
    return FinanceTransactionsResponse(items=[FinanceTransactionItem(**row) for row in rows])
