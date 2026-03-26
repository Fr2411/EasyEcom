from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class FinanceTransaction(BaseModel):
    entry_id: str
    entry_date: str
    entry_type: str
    category: str
    amount: float
    direction: str  # 'in' or 'out'
    reference: str
    note: str


class TransactionListResponse(BaseModel):
    transactions: List[FinanceTransaction]
    total: int
    limit: int
    offset: int


class CreateTransactionRequest(BaseModel):
    entry_type: str = Field(..., description="Type of transaction: 'payment' or 'expense'")
    entry_date: Optional[str] = Field(None, description="Date of transaction (ISO format)")
    category: str = Field(..., description="Category of transaction")
    amount: float = Field(..., gt=0, description="Amount of transaction")
    direction: str = Field(..., description="Direction: 'in' for income, 'out' for expense")
    reference: str = Field("", description="Reference number or identifier")
    note: str = Field("", description="Additional notes")
    vendor_name: Optional[str] = Field(None, description="Vendor name (for expenses)")
    payment_status: Optional[str] = Field(None, description="Payment status (for expenses)")


class UpdateTransactionRequest(BaseModel):
    entry_type: str = Field(..., description="Type of transaction: 'payment' or 'expense'")
    entry_date: Optional[str] = Field(None, description="Date of transaction (ISO format)")
    category: Optional[str] = Field(None, description="Category of transaction")
    amount: Optional[float] = Field(None, gt=0, description="Amount of transaction")
    direction: Optional[str] = Field(None, description="Direction: 'in' for income, 'out' for expense")
    reference: Optional[str] = Field(None, description="Reference number or identifier")
    note: Optional[str] = Field(None, description="Additional notes")
    vendor_name: Optional[str] = Field(None, description="Vendor name (for expenses)")
    payment_status: Optional[str] = Field(None, description="Payment status (for expenses)")


class FinanceOverviewResponse(BaseModel):
    sales_revenue: Optional[float] = None
    expense_total: Optional[float] = None
    receivables: Optional[float] = None
    payables: Optional[float] = None
    cash_in: Optional[float] = None
    cash_out: Optional[float] = None
    net_operating: Optional[float] = None