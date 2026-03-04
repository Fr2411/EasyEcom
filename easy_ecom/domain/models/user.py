from pydantic import BaseModel


class UserCreate(BaseModel):
    client_id: str
    name: str
    email: str
    password: str
    role_code: str
