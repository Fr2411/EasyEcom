from pydantic import BaseModel


class ClientCreate(BaseModel):
    business_name: str
    owner_name: str
    phone: str = ""
    email: str
    address: str = ""
