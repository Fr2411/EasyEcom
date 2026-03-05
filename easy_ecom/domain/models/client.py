from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    business_name: str
    owner_name: str
    phone: str = ""
    email: str
    address: str = ""
    currency_code: str = Field(min_length=3, max_length=3)
    currency_symbol: str = ""


class ClientUpdate(BaseModel):
    business_name: str
    owner_name: str
    phone: str = ""
    email: str
    address: str = ""
    currency_code: str = Field(min_length=3, max_length=3)
    currency_symbol: str = ""
    status: str = "active"
    notes: str = ""
