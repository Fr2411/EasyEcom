from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AdminRoleAccessResponse(BaseModel):
    role_code: str
    role_name: str
    description: str
    allowed_pages: list[str]


class AdminRolesResponse(BaseModel):
    items: list[AdminRoleAccessResponse]


class AdminAuditItemResponse(BaseModel):
    audit_log_id: str
    client_id: str | None
    entity_type: str
    entity_id: str
    action: str
    actor_user_id: str | None
    created_at: str
    metadata_json: dict[str, Any] | None = None


class AdminAuditResponse(BaseModel):
    items: list[AdminAuditItemResponse]


class AdminClientResponse(BaseModel):
    client_id: str
    client_code: str
    business_name: str
    contact_name: str
    owner_name: str
    email: str
    phone: str
    address: str
    website_url: str
    facebook_url: str
    instagram_url: str
    whatsapp_number: str
    status: str
    notes: str
    timezone: str
    currency_code: str
    currency_symbol: str
    default_location_name: str
    created_at: str
    updated_at: str


class AdminClientsResponse(BaseModel):
    items: list[AdminClientResponse]


class AdminUserResponse(BaseModel):
    user_id: str
    user_code: str
    client_id: str
    client_code: str
    name: str
    email: str
    role_code: str
    role_name: str
    is_active: bool
    created_at: str
    last_login_at: str | None = None


class AdminUsersResponse(BaseModel):
    items: list[AdminUserResponse]


class AdminOnboardUserInput(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: str
    role_code: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=255)


class AdminOnboardClientRequest(BaseModel):
    business_name: str = Field(min_length=2, max_length=255)
    contact_name: str = Field(min_length=2, max_length=255)
    primary_email: str
    primary_phone: str = Field(min_length=3, max_length=64)
    owner_name: str = Field(min_length=2, max_length=255)
    owner_email: str
    owner_password: str = Field(min_length=6, max_length=255)
    address: str = ""
    website_url: str = ""
    facebook_url: str = ""
    instagram_url: str = ""
    whatsapp_number: str = ""
    notes: str = ""
    timezone: str | None = None
    currency_code: str | None = None
    currency_symbol: str | None = None
    default_location_name: str | None = None
    additional_users: list[AdminOnboardUserInput] = Field(default_factory=list)


class AdminOnboardResponse(BaseModel):
    client: AdminClientResponse
    users: list[AdminUserResponse]
    warnings: list[str]


class AdminClientUpdateRequest(BaseModel):
    business_name: str | None = Field(default=None, min_length=2, max_length=255)
    contact_name: str | None = Field(default=None, min_length=2, max_length=255)
    owner_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: str | None = None
    phone: str | None = Field(default=None, min_length=3, max_length=64)
    address: str | None = None
    website_url: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    whatsapp_number: str | None = None
    notes: str | None = None
    timezone: str | None = None
    currency_code: str | None = None
    currency_symbol: str | None = None
    status: str | None = None
    default_location_name: str | None = None


class AdminUserCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: str
    role_code: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=255)


class AdminUserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    role_code: str | None = Field(default=None, min_length=3, max_length=64)
    is_active: bool | None = None


class AdminUserPasswordSetRequest(BaseModel):
    password: str = Field(min_length=6, max_length=255)
