from pydantic import BaseModel, Field


class LedgerEntryCreate(BaseModel):
    client_id: str
    entry_type: str
    category: str
    amount: float = Field(gt=0)
    source_type: str
    source_id: str
    note: str = ""
