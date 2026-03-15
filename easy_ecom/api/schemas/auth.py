from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    user_id: str
    client_id: str
    roles: str
    allowed_pages: list[str]
    name: str
    email: str


class CurrentUserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    business_name: str | None = None
    role: str
    client_id: str
    roles: list[str]
    allowed_pages: list[str]
    is_authenticated: bool
