from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)


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


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetIssueResponse(BaseModel):
    accepted: bool
    delivery: str
    reset_token: str | None = None
    expires_at: str | None = None


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=12)
    new_password: str = Field(min_length=6)


class InvitationIssueRequest(BaseModel):
    client_id: str
    email: str
    role_code: str = Field(min_length=3, max_length=64)


class InvitationIssueResponse(BaseModel):
    invitation_id: str
    invitation_token: str
    expires_at: str


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=12)
    name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=6)
