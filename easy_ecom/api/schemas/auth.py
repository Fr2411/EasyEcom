from pydantic import BaseModel



class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    user_id: str
    client_id: str
    roles: str
    name: str
    email: str


class CurrentUserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    client_id: str
    roles: list[str]
    is_authenticated: bool
