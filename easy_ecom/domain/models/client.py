from pydantic import BaseModel, EmailStr


class ClientCreate(BaseModel):
    business_name: str
    owner_name: str
    phone: str = ""
    email: EmailStr
    address: str = ""
