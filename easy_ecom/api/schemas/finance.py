from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

FinanceOriginType = Literal["sale_fulfillment", "return_refund", "manual_payment", "manual_expense"]
PaymentDirection = Literal["in", "out"]
FinanceStatus = Literal["posted", "paid", "unpaid", "partial", "pending", "completed", "reversed"]
CounterpartyType = Literal["customer", "vendor", "internal"]


class FinanceTransaction(BaseModel):
    transaction_id: str
    origin_type: FinanceOriginType
    origin_id: Optional[str] = None
    occurred_at: str
    direction: PaymentDirection
    status: FinanceStatus
    amount: float
    currency_code: str
    reference: str
    note: str
    counterparty_type: Optional[CounterpartyType] = None
    counterparty_id: Optional[str] = None
    counterparty_name: str
    editable: bool = False
    source_label: str = ""


class TransactionListResponse(BaseModel):
    transactions: List[FinanceTransaction]
    total: int
    limit: int
    offset: int


class CreateTransactionRequest(BaseModel):
    origin_type: Literal["manual_payment", "manual_expense"] = Field(..., description="Manual finance transaction type")
    occurred_at: Optional[str] = Field(None, description="Date of transaction (ISO format)")
    amount: float = Field(..., gt=0, description="Amount of transaction")
    direction: PaymentDirection = Field(..., description="Direction: 'in' for inflow, 'out' for outflow")
    status: Optional[FinanceStatus] = Field(None, description="Settlement status for the manual transaction")
    currency_code: Optional[str] = Field(None, description="Currency code")
    reference: str = Field("", description="Reference number or identifier")
    note: str = Field("", description="Additional notes")
    counterparty_name: Optional[str] = Field(None, description="Customer, vendor, or internal counterparty name")
    counterparty_type: Optional[CounterpartyType] = Field(None, description="Counterparty type")


class UpdateTransactionRequest(BaseModel):
    origin_type: Literal["manual_payment", "manual_expense"] = Field(..., description="Manual finance transaction type")
    occurred_at: Optional[str] = Field(None, description="Date of transaction (ISO format)")
    amount: Optional[float] = Field(None, gt=0, description="Amount of transaction")
    direction: Optional[PaymentDirection] = Field(None, description="Direction: 'in' for inflow, 'out' for outflow")
    status: Optional[FinanceStatus] = Field(None, description="Settlement status for the manual transaction")
    currency_code: Optional[str] = Field(None, description="Currency code")
    reference: Optional[str] = Field(None, description="Reference number or identifier")
    note: Optional[str] = Field(None, description="Additional notes")
    counterparty_name: Optional[str] = Field(None, description="Customer, vendor, or internal counterparty name")
    counterparty_type: Optional[CounterpartyType] = Field(None, description="Counterparty type")


class FinanceOverviewResponse(BaseModel):
    revenue: Optional[float] = None
    cash_collected: Optional[float] = None
    refunds_paid: Optional[float] = None
    expenses: Optional[float] = None
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
    transaction_id: str
    reference: str
    vendor_name: str
    origin_type: FinanceOriginType
    occurred_at: str
    amount: float
    status: str
    note: str


class FinanceWorkspaceResponse(BaseModel):
    overview: FinanceOverviewResponse
    commerce_transactions: List[FinanceTransaction]
    manual_transactions: List[FinanceTransaction]
    receivables: List[FinanceReceivable]
    payables: List[FinancePayable]
    recent_refunds: List[FinanceTransaction]
