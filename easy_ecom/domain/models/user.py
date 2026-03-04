from pydantic import BaseModel, field_validator

from easy_ecom.domain.models.validators import validate_email_format


class UserCreate(BaseModel):
    client_id: str
    name: str
    email: str
    password: str
    role_code: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return validate_email_format(value)
