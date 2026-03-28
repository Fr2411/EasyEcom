from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

TransactionType = Literal["payment", "expense"]
PaymentDirection = Literal["in", "out"]
PaymentStatus = Literal["paid", "unpaid", "partial", "completed", "pending", "succeeded"]


class FinanceTransaction(BaseModel):
    entry_id: str
    entry_date: str
    entry_type: TransactionType
    direction: PaymentDirection
    category: str
    amount: float
    reference: str
    note: str
    payment_status: Optional[PaymentStatus] = None
    vendor_name: Optional[str] = None


class TransactionListResponse(BaseModel):
    transactions: List[FinanceTransaction]
    total: int
    limit: int
    offset: int


class CreateTransactionRequest(BaseModel):
    entry_type: TransactionType = Field(..., description="Type of transaction: 'payment' or 'expense'")
    entry_date: Optional[str] = Field(None, description="Date of transaction (ISO format)")
    category: str = Field(..., description="Category of transaction")
    amount: float = Field(..., gt=0, description="Amount of transaction")
    direction: PaymentDirection = Field(..., description="Direction: 'in' for income, 'out' for expense")
    reference: str = Field("", description="Reference number or identifier")
    note: str = Field("", description="Additional notes")
    vendor_name: Optional[str] = Field(None, description="Vendor name (for expenses)")
    payment_status: Optional[PaymentStatus] = Field(None, description="Payment status (for expenses)")


class UpdateTransactionRequest(BaseModel):
    entry_type: TransactionType = Field(..., description="Type of transaction: 'payment' or 'expense'")
    entry_date: Optional[str] = Field(None, description="Date of transaction (ISO format)")
    category: Optional[str] = Field(None, description="Category of transaction")
    amount: Optional[float] = Field(None, gt=0, description="Amount of transaction")
    direction: Optional[PaymentDirection] = Field(None, description="Direction: 'in' for income, 'out' for expense")
    reference: Optional[str] = Field(None, description="Reference number or identifier")
    note: Optional[str] = Field(None, description="Additional notes")
    vendor_name: Optional[str] = Field(None, description="Vendor name (for expenses)")
    payment_status: Optional[PaymentStatus] = Field(None, description="Payment status (for expenses)")


class FinanceOverviewResponse(BaseModel):
    sales_revenue: Optional[float] = None
    expense_total: Optional[float] = None
    receivables: Optional[float] = None
    payables: Optional[float] = None
    cash_in: Optional[float] = None
    cash_out: Optional[float] = None
    net_operating: Optional[float] = None


class FinanceReceivable(BaseModel):
    sale_id: str
    sale_no: str
    customer_id: Optional[str] = None
    customer_name: str
    sale_date: str
    grand_total: float
    amount_paid: float
    outstanding_balance: float
    payment_status: str


class FinancePayable(BaseModel):
    expense_id: str
    expense_number: str
    vendor_name: str
    category: str
    expense_date: str
    amount: float
    payment_status: str
    note: str


class FinanceWorkspaceResponse(BaseModel):
    overview: FinanceOverviewResponse
    transactions: List[FinanceTransaction]
    receivables: List[FinanceReceivable]
    payables: List[FinancePayable]
