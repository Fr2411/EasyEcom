from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)


class SignupRequest(BaseModel):
    business_name: str = Field(min_length=2, max_length=255)
    name: str = Field(min_length=2, max_length=255)
    email: str
    phone: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=255)


class LoginResponse(BaseModel):
    user_id: str
    client_id: str
    roles: str
    allowed_pages: list[str]
    name: str
    email: str
    billing_plan_code: str = "free"
    billing_status: str = "free"
    billing_access_state: str = "free_active"
    billing_grace_until: str | None = None


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
    billing_plan_code: str = "free"
    billing_status: str = "free"
    billing_access_state: str = "free_active"
    billing_grace_until: str | None = None
