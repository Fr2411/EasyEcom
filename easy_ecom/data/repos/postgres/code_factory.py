from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from easy_ecom.core.slugs import slugify_identifier, with_suffix
from easy_ecom.data.store.postgres_models import ClientModel, UserModel


CLIENT_CODE_MAX_LENGTH = 64
USER_CODE_MAX_LENGTH = 160

ROLE_CODE_SLUGS = {
    "SUPER_ADMIN": "super-admin",
    "CLIENT_OWNER": "client-owner",
    "CLIENT_STAFF": "client-staff",
    "FINANCE_STAFF": "finance-staff",
}


def role_code_slug(role_code: str) -> str:
    return ROLE_CODE_SLUGS.get(
        role_code,
        slugify_identifier(role_code, max_length=40, default="user-role"),
    )


def generate_unique_client_code(session: Session, business_name: str) -> str:
    base = slugify_identifier(business_name, max_length=CLIENT_CODE_MAX_LENGTH, default="client")
    index = 1
    while True:
        candidate = with_suffix(base, index, max_length=CLIENT_CODE_MAX_LENGTH)
        existing = session.execute(
            select(ClientModel.client_id).where(ClientModel.slug == candidate)
        ).scalar_one_or_none()
        if existing is None:
            return candidate
        index += 1


def generate_unique_user_code(session: Session, client_code: str, role_code: str, name: str) -> str:
    base = slugify_identifier(
        f"{client_code}-{role_code_slug(role_code)}-{name}",
        max_length=USER_CODE_MAX_LENGTH,
        default="user",
    )
    index = 1
    while True:
        candidate = with_suffix(base, index, max_length=USER_CODE_MAX_LENGTH)
        existing = session.execute(
            select(UserModel.user_id).where(UserModel.user_code == candidate)
        ).scalar_one_or_none()
        if existing is None:
            return candidate
        index += 1
