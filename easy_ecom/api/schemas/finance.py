from pydantic import BaseModel, Field


class FinanceOverviewResponse(BaseModel):
    sales_revenue: float | None = None
    expense_total: float | None = None
    receivables: float | None = None
    payables: float | None = None
    cash_in: float | None = None
    cash_out: float | None = None
    net_operating: float | None = None


class ExpenseItem(BaseModel):
    expense_id: str
    expense_date: str
    category: str
    amount: float
    payment_status: str
    note: str = ""
    created_at: str = ""
    updated_at: str = ""


class ExpenseListResponse(BaseModel):
    items: list[ExpenseItem]


class ExpenseCreateRequest(BaseModel):
    expense_date: str = Field(min_length=10, max_length=10)
    category: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0)
    payment_status: str = Field(default="paid")
    note: str = Field(default="", max_length=500)


class ExpenseUpdateRequest(ExpenseCreateRequest):
    pass


class ExpenseMutationResponse(BaseModel):
    expense: ExpenseItem


class ReceivableItem(BaseModel):
    sale_id: str
    sale_no: str
    customer_id: str
    customer_name: str
    sale_date: str
    grand_total: float
    amount_paid: float
    outstanding_balance: float
    payment_status: str


class ReceivablesResponse(BaseModel):
    items: list[ReceivableItem]


class PayablesResponse(BaseModel):
    supported: bool
    deferred_reason: str = ""
    unpaid_count: int = 0
    rows: list[ExpenseItem] = []


class FinanceTransactionItem(BaseModel):
    entry_id: str
    entry_date: str
    entry_type: str
    category: str
    amount: float
    direction: str
    reference: str
    note: str = ""


class FinanceTransactionsResponse(BaseModel):
    items: list[FinanceTransactionItem]
