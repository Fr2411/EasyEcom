from decimal import Decimal

from pydantic import BaseModel


class CustomerWorkspaceRecentOrderResponse(BaseModel):
    sales_order_id: str
    order_number: str
    status: str
    payment_status: str
    total_amount: Decimal
    ordered_at: str | None


class CustomerWorkspaceRecentReturnResponse(BaseModel):
    sales_return_id: str
    return_number: str
    order_number: str
    refund_status: str
    refund_amount: Decimal
    requested_at: str | None


class CustomerWorkspaceItemResponse(BaseModel):
    customer_id: str
    name: str
    phone: str
    email: str
    address: str
    total_orders: int
    completed_orders: int
    open_orders: int
    total_returns: int
    lifetime_revenue: Decimal
    outstanding_balance: Decimal
    last_order_at: str | None
    last_return_at: str | None
    recent_orders: list[CustomerWorkspaceRecentOrderResponse]
    recent_returns: list[CustomerWorkspaceRecentReturnResponse]


class CustomerWorkspaceResponse(BaseModel):
    query: str = ''
    items: list[CustomerWorkspaceItemResponse]
