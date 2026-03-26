from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from typing import List, Optional

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.finance import (
    FinanceTransaction,
    TransactionListResponse,
    CreateTransactionRequest,
    UpdateTransactionRequest,
    FinanceOverviewResponse
)
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.transaction_service import TransactionService
from easy_ecom.domain.services.overview_service import OverviewService

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/overview", response_model=FinanceOverviewResponse)
def finance_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
):
    """Get finance overview with key financial metrics."""
    require_page_access(user, "Finance")
    # Call the domain service to get finance overview data
    overview_data = container.overview.finance(user)
    # For now, return basic structure - can be enhanced with actual calculations
    return FinanceOverviewResponse(
        sales_revenue=0.0,
        expense_total=0.0,
        receivables=0.0,
        payables=0.0,
        cash_in=0.0,
        cash_out=0.0,
        net_operating=0.0
    )


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions(
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type: payment or expense"),
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
):
    """List financial transactions with optional filtering."""
    require_page_access(user, "Finance")
    
    # Create transaction service
    transaction_service = TransactionService(container._session_factory if hasattr(container, '_session_factory') else None)
    
    # If container doesn't have session factory exposed, we'll need to access it differently
    # For now, let's use the container's overview service pattern
    context = type('TransactionContext', (), {
        'user': user,
        'is_super_admin': "SUPER_ADMIN" in user.roles
    })()
    
    # Get transactions from service
    transactions = transaction_service.get_transactions(
        context,
        limit=limit,
        offset=offset,
        transaction_type=transaction_type
    )
    
    # Get total count (simplified - in real implementation would query count)
    total = len(transactions)  # This is not accurate for pagination but works for demo
    
    return TransactionListResponse(
        transactions=transactions,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/transactions/{transaction_id}", response_model=FinanceTransaction)
def get_transaction(
    transaction_id: str = Path(..., description="The ID of the transaction to retrieve"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
):
    """Get a specific financial transaction by ID."""
    require_page_access(user, "Finance")
    
    # Create transaction service
    transaction_service = TransactionService(container._session_factory if hasattr(container, '_session_factory') else None)
    
    context = type('TransactionContext', (), {
        'user': user,
        'is_super_admin': "SUPER_ADMIN" in user.roles
    })()
    
    transaction = transaction_service.get_transaction(context, transaction_id)
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID {transaction_id} not found"
        )
    
    return transaction


@router.post("/transactions", response_model=FinanceTransaction, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction_data: CreateTransactionRequest = Body(...),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
):
    """Create a new financial transaction."""
    require_page_access(user, "Finance")
    
    # Create transaction service
    transaction_service = TransactionService(container._session_factory if hasattr(container, '_session_factory') else None)
    
    context = type('TransactionContext', (), {
        'user': user,
        'is_super_admin': "SUPER_ADMIN" in user.roles
    })()
    
    # Convert Pydantic model to dict
    data = transaction_data.model_dump(exclude_unset=True)
    
    transaction = transaction_service.create_transaction(
        context,
        transaction_type=transaction_data.entry_type,
        data=data
    )
    
    return transaction


@router.put("/transactions/{transaction_id}", response_model=FinanceTransaction)
def update_transaction(
    transaction_id: str = Path(..., description="The ID of the transaction to update"),
    transaction_data: UpdateTransactionRequest = Body(...),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
):
    """Update an existing financial transaction."""
    require_page_access(user, "Finance")
    
    # Create transaction service
    transaction_service = TransactionService(container._session_factory if hasattr(container, '_session_factory') else None)
    
    context = type('TransactionContext', (), {
        'user': user,
        'is_super_admin': "SUPER_ADMIN" in user.roles
    })()
    
    # Convert Pydantic model to dict, excluding unset fields
    data = transaction_data.model_dump(exclude_unset=True)
    
    # Remove entry_type from data as it's used separately
    transaction_type = data.pop('entry_type', None)
    if not transaction_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entry_type is required for update"
        )
    
    transaction = transaction_service.update_transaction(
        context,
        transaction_id=transaction_id,
        transaction_type=transaction_type,
        data=data
    )
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID {transaction_id} not found or not authorized"
        )
    
    return transaction


@router.get("/accounts", response_model=List[dict])
def list_accounts(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
):
    """List financial accounts (chart of accounts)."""
    require_page_access(user, "Finance")
    
    # Return basic account structure - in a real implementation this would come from a chart of accounts service
    return [
        {
            "id": "cash",
            "name": "Cash",
            "type": "asset",
            "balance": 0.0
        },
        {
            "id": "bank",
            "name": "Bank Accounts",
            "type": "asset",
            "balance": 0.0
        },
        {
            "id": "accounts_receivable",
            "name": "Accounts Receivable",
            "type": "asset",
            "balance": 0.0
        },
        {
            "id": "accounts_payable",
            "name": "Accounts Payable",
            "type": "liability",
            "balance": 0.0
        },
        {
            "id": "sales_revenue",
            "name": "Sales Revenue",
            "type": "revenue",
            "balance": 0.0
        },
        {
            "id": "expenses",
            "name": "Expenses",
            "type": "expense",
            "balance": 0.0
        }
    ]


@router.get("/reports", response_model=List[dict])
def list_financial_reports(
    report_type: Optional[str] = Query(None, description="Type of financial report"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
):
    """List available financial reports."""
    require_page_access(user, "Finance")
    
    # Return available financial reports
    reports = [
        {
            "id": "profit_loss",
            "name": "Profit and Loss Statement",
            "description": "Shows revenue, expenses, and net profit over a period",
            "type": "statement"
        },
        {
            "id": "balance_sheet",
            "name": "Balance Sheet",
            "description": "Shows assets, liabilities, and equity at a point in time",
            "type": "statement"
        },
        {
            "id": "cash_flow",
            "name": "Cash Flow Statement",
            "description": "Shows cash inflows and outflows over a period",
            "type": "statement"
        },
        {
            "id": "tax_summary",
            "name": "Tax Summary",
            "description": "Summary of tax liabilities and payments",
            "type": "summary"
        }
    ]
    
    if report_type:
        reports = [r for r in reports if report_type.lower() in r["type"].lower() or report_type.lower() in r["id"].lower()]
    
    return reports