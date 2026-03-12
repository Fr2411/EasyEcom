from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from easy_ecom.domain.services.admin_api_service import DEFAULT_ROLE_CODES


class AdminUserRecord(BaseModel):
    user_id: str
    client_id: str
    name: str
    email: str
    is_active: bool
    created_at: str
    roles: list[str]


class AdminUsersResponse(BaseModel):
    items: list[AdminUserRecord]


class AdminRolesResponse(BaseModel):
    roles: list[str]


class AdminAuditResponse(BaseModel):
    supported: bool
    deferred_reason: str
    items: list[dict[str, str]] = Field(default_factory=list)


class AdminCreateUserRequest(BaseModel):
    client_id: str | None = Field(default=None, min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    role_codes: list[str] = Field(min_length=1)
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        text = value.strip().lower()
        if "@" not in text:
            raise ValueError("email must contain '@'")
        return text

    @field_validator("role_codes")
    @classmethod
    def validate_roles(cls, value: list[str]) -> list[str]:
        cleaned = sorted({role.strip() for role in value if role.strip()})
        if not cleaned:
            raise ValueError("At least one role is required")
        invalid = [role for role in cleaned if role not in DEFAULT_ROLE_CODES]
        if invalid:
            raise ValueError(f"Invalid role code(s): {', '.join(invalid)}")
        return cleaned


class AdminUpdateUserRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip().lower()
        if "@" not in text:
            raise ValueError("email must contain '@'")
        return text


class AdminSetRolesRequest(BaseModel):
    role_codes: list[str] = Field(min_length=1)

    @field_validator("role_codes")
    @classmethod
    def validate_roles(cls, value: list[str]) -> list[str]:
        cleaned = sorted({role.strip() for role in value if role.strip()})
        if not cleaned:
            raise ValueError("At least one role is required")
        invalid = [role for role in cleaned if role not in DEFAULT_ROLE_CODES]
        if invalid:
            raise ValueError(f"Invalid role code(s): {', '.join(invalid)}")
        return cleaned




class AdminCreateTenantRequest(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)
    owner_name: str = Field(min_length=1, max_length=255)
    owner_email: str = Field(min_length=3, max_length=255)
    owner_password: str = Field(min_length=8, max_length=255)
    currency_code: str = Field(min_length=3, max_length=3)

    @field_validator("owner_email")
    @classmethod
    def validate_owner_email(cls, value: str) -> str:
        text = value.strip().lower()
        if "@" not in text:
            raise ValueError("owner_email must contain '@'")
        return text

    @field_validator("currency_code")
    @classmethod
    def validate_currency_code(cls, value: str) -> str:
        return value.strip().upper()


class AdminTenantCreateResponse(BaseModel):
    client_id: str
    business_name: str
    owner_user: AdminUserRecord


class AdminUserMutationResponse(BaseModel):
    user: AdminUserRecord
