from pydantic import BaseModel


class CustomerCreate(BaseModel):
    client_id: str
    full_name: str
    phone: str = ""
    email: str = ""
    address_line1: str = ""
    city: str = ""
    country: str = ""
