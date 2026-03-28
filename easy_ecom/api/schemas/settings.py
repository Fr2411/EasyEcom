from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class SettingsTenantContextResponse(BaseModel):
    client_id: str
    business_name: str
    status: str
    currency_code: str


class SettingsProfileResponse(BaseModel):
    business_name: str
    contact_name: str
    owner_name: str
    email: str
    phone: str
    address: str
    website_url: str
    whatsapp_number: str
    timezone: str
    currency_code: str
    currency_symbol: str
    notes: str


class SettingsDefaultsResponse(BaseModel):
    default_location_name: str
    low_stock_threshold: float
    allow_backorder: bool
    require_discount_approval: bool


class SettingsPrefixesResponse(BaseModel):
    sales_prefix: str
    purchases_prefix: str
    returns_prefix: str


class SettingsWorkspaceResponse(BaseModel):
    tenant_context: SettingsTenantContextResponse
    profile: SettingsProfileResponse
    defaults: SettingsDefaultsResponse
    prefixes: SettingsPrefixesResponse


class SettingsProfileUpdate(BaseModel):
    business_name: str = Field(min_length=2, max_length=255)
    contact_name: str = ""
    owner_name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    website_url: str = ""
    whatsapp_number: str = ""
    timezone: str = Field(min_length=2, max_length=64)
    currency_code: str = Field(min_length=3, max_length=16)
    currency_symbol: str = Field(min_length=1, max_length=8)
    notes: str = ""

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalize_currency_code(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class SettingsDefaultsUpdate(BaseModel):
    default_location_name: str = Field(min_length=2, max_length=128)
    low_stock_threshold: Decimal = Field(ge=Decimal("0"))
    allow_backorder: bool = False
    require_discount_approval: bool = False


class SettingsPrefixesUpdate(BaseModel):
    sales_prefix: str = Field(min_length=1, max_length=16)
    purchases_prefix: str = Field(min_length=1, max_length=16)
    returns_prefix: str = Field(min_length=1, max_length=16)

    @field_validator("sales_prefix", "purchases_prefix", "returns_prefix", mode="before")
    @classmethod
    def normalize_prefix(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class SettingsWorkspaceUpdateRequest(BaseModel):
    profile: SettingsProfileUpdate
    defaults: SettingsDefaultsUpdate
    prefixes: SettingsPrefixesUpdate
