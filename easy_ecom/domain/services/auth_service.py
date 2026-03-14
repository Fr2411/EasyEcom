from __future__ import annotations

from dataclasses import dataclass

from easy_ecom.core.security import hash_password, verify_password
from easy_ecom.core.time_utils import now_utc
from easy_ecom.domain.models.auth import AuthenticatedUser


@dataclass(frozen=True)
class AuthUserRecord:
    user_id: str
    client_id: str
    name: str
    email: str
    password: str
    password_hash: str
    is_active: bool


class AuthRepoProtocol:
    def get_user_by_email(self, email: str) -> AuthUserRecord | None: ...

    def get_roles_for_user(self, user_id: str) -> list[str]: ...

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

        self.repo.touch_last_login(user.user_id, now_utc())
        return AuthenticatedUser(
            user_id=user.user_id,
            client_id=user.client_id,
            name=user.name,
            email=user.email,
            roles=roles,
        )
