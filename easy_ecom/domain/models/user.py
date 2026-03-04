from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    client_id: str
    name: str
    email: EmailStr
    password: str
    role_code: str
