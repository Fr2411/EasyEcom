from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomerBasePayload(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(default="", max_length=64)
    email: str = Field(default="", max_length=255)
    address_line1: str = Field(default="", max_length=255)
    city: str = Field(default="", max_length=128)
    notes: str = Field(default="", max_length=2000)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        text = value.strip()
        if text and "@" not in text:
            raise ValueError("email must contain '@'")
        return text


class CustomerCreateRequest(CustomerBasePayload):
    pass


class CustomerUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    address_line1: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if text and "@" not in text:
            raise ValueError("email must contain '@'")
        return text


class CustomerRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    customer_id: str
    full_name: str
    phone: str
    email: str
    address_line1: str
    city: str
    notes: str
    is_active: bool
    created_at: str
    updated_at: str


class CustomerListResponse(BaseModel):
    items: list[CustomerRecord]


class CustomerMutationResponse(BaseModel):
    customer: CustomerRecord
