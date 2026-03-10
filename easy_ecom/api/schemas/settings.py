from pydantic import BaseModel, Field


class BusinessProfileResponse(BaseModel):
    client_id: str
    business_name: str
    display_name: str
    phone: str
    email: str
    address: str
    currency_code: str
    timezone: str
    tax_registration_no: str
    logo_upload_supported: bool
    logo_upload_deferred_reason: str


class BusinessProfilePatchRequest(BaseModel):
    business_name: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=1000)
    currency_code: str | None = Field(default=None, max_length=16)
    timezone: str | None = Field(default=None, max_length=64)
    tax_registration_no: str | None = Field(default=None, max_length=120)


class PreferencesActiveUsage(BaseModel):
    low_stock_threshold: bool
    default_sales_note: bool
    default_inventory_adjustment_reasons: bool
    default_payment_terms_days: bool


class PreferencesResponse(BaseModel):
    low_stock_threshold: int
    default_sales_note: str
    default_inventory_adjustment_reasons: list[str]
    default_payment_terms_days: int
    active_usage: PreferencesActiveUsage


class PreferencesPatchRequest(BaseModel):
    low_stock_threshold: int | None = Field(default=None, ge=0, le=999)
    default_sales_note: str | None = Field(default=None, max_length=500)
    default_inventory_adjustment_reasons: list[str] | None = Field(default=None, max_length=20)
    default_payment_terms_days: int | None = Field(default=None, ge=0, le=365)


class SequenceActiveUsage(BaseModel):
    sales_prefix: bool
    returns_prefix: bool
    purchases_prefix: bool


class SequenceResponse(BaseModel):
    sales_prefix: str
    returns_prefix: str
    purchases_prefix: str
    active_usage: SequenceActiveUsage


class SequencePatchRequest(BaseModel):
    sales_prefix: str | None = Field(default=None, min_length=1, max_length=20)
    returns_prefix: str | None = Field(default=None, min_length=1, max_length=20)
    purchases_prefix: str | None = Field(default=None, min_length=1, max_length=20)


class TenantContextResponse(BaseModel):
    client_id: str
    business_name: str
    status: str
    currency_code: str
