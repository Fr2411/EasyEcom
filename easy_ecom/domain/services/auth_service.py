from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from easy_ecom.core.rbac import effective_page_names
from easy_ecom.core.security import hash_password, verify_password
from easy_ecom.core.time_utils import now_utc
from easy_ecom.domain.models.auth import AuthenticatedUser


@dataclass(frozen=True)
class AuthUserRecord:
    user_id: str
    client_id: str
    name: str
    email: str
    business_name: str | None
    password: str
    password_hash: str
    is_active: bool


@dataclass(frozen=True)
class AuthPageOverrideRecord:
    page_code: str
    is_allowed: bool


class AuthRepoProtocol:
    def get_user_by_email(self, email: str) -> AuthUserRecord | None: ...

    def get_roles_for_user(self, user_id: str) -> list[str]: ...

    def get_page_access_overrides(self, user_id: str) -> list[AuthPageOverrideRecord]: ...

    def update_password_hash(self, user_id: str, password_hash: str) -> None: ...

    def touch_last_login(self, user_id: str, logged_in_at: datetime) -> None: ...


class AuthService:
    def __init__(self, repo: AuthRepoProtocol):
        self.repo = repo

    def authenticate(self, email: str, password: str) -> AuthenticatedUser | None:
        user = self.repo.get_user_by_email(email)
        if user is None or not user.is_active:
            return None

        if user.password_hash:
            is_valid = verify_password(password, user.password_hash)
        else:
            is_valid = password == user.password
            if is_valid:
                self.repo.update_password_hash(user.user_id, hash_password(password))

        if not is_valid:
            return None

        roles = self.repo.get_roles_for_user(user.user_id)
        if not roles:
            return None
        overrides = self.repo.get_page_access_overrides(user.user_id)
        granted_page_codes = [item.page_code for item in overrides if item.is_allowed]
        revoked_page_codes = [item.page_code for item in overrides if not item.is_allowed]
        allowed_pages = list(effective_page_names(roles, granted_page_codes, revoked_page_codes))

        self.repo.touch_last_login(user.user_id, now_utc())
        return AuthenticatedUser(
            user_id=user.user_id,
            client_id=user.client_id,
            name=user.name,
            email=user.email,
            business_name=user.business_name,
            roles=roles,
            allowed_pages=allowed_pages,
        )
