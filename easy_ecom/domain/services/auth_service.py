from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from easy_ecom.core.security import hash_password, hash_token, new_token, verify_password
from easy_ecom.core.time_utils import ensure_utc, now_utc
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


@dataclass(frozen=True)
class PasswordResetRecord:
    reset_token_id: str
    user_id: str
    expires_at: datetime
    consumed_at: datetime | None


@dataclass(frozen=True)
class InvitationRecord:
    invitation_id: str
    client_id: str
    email: str
    role_code: str
    expires_at: datetime
    accepted_at: datetime | None
    status: str


@dataclass(frozen=True)
class IssuedToken:
    record_id: str
    plain_token: str
    expires_at: datetime


class AuthRepoProtocol:
    def get_user_by_email(self, email: str) -> AuthUserRecord | None: ...

    def get_user_by_client_email(self, client_id: str, email: str) -> AuthUserRecord | None: ...

    def get_roles_for_user(self, user_id: str) -> list[str]: ...

    def update_password_hash(self, user_id: str, password_hash: str) -> None: ...

    def activate_invited_user(
        self,
        *,
        client_id: str,
        email: str,
        name: str,
        password_hash: str,
        invited_at: datetime,
    ) -> AuthenticatedUser | None: ...

    def ensure_user_role(self, user_id: str, role_code: str) -> None: ...

    def touch_last_login(self, user_id: str, logged_in_at: datetime) -> None: ...

    def create_password_reset_token(self, user_id: str, token_hash: str, expires_at: datetime) -> str: ...

    def get_password_reset_by_token_hash(self, token_hash: str) -> PasswordResetRecord | None: ...

    def mark_password_reset_consumed(self, reset_token_id: str, consumed_at: datetime) -> None: ...

    def create_invitation(
        self,
        client_id: str,
        email: str,
        role_code: str,
        invited_by_user_id: str,
        token_hash: str,
        expires_at: datetime,
    ) -> str: ...

    def get_invitation_by_token_hash(self, token_hash: str) -> InvitationRecord | None: ...

    def mark_invitation_accepted(self, invitation_id: str, accepted_at: datetime) -> None: ...

    def create_user(
        self,
        *,
        client_id: str,
        name: str,
        email: str,
        password_hash: str,
        role_code: str,
        invited_at: datetime | None = None,
    ) -> AuthenticatedUser: ...


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

    def issue_password_reset(self, email: str, ttl_minutes: int) -> IssuedToken | None:
        user = self.repo.get_user_by_email(email)
        if user is None or not user.is_active:
            return None

        plain_token = new_token(24)
        expires_at = now_utc() + timedelta(minutes=max(ttl_minutes, 5))
        record_id = self.repo.create_password_reset_token(
            user.user_id,
            hash_token(plain_token),
            expires_at,
        )
        return IssuedToken(record_id=record_id, plain_token=plain_token, expires_at=expires_at)

    def reset_password(self, token: str, new_password: str) -> bool:
        record = self.repo.get_password_reset_by_token_hash(hash_token(token))
        if record is None or record.consumed_at is not None or ensure_utc(record.expires_at) < now_utc():
            return False

        self.repo.update_password_hash(record.user_id, hash_password(new_password))
        self.repo.mark_password_reset_consumed(record.reset_token_id, now_utc())
        return True

    def issue_invitation(
        self,
        *,
        client_id: str,
        email: str,
        role_code: str,
        invited_by_user_id: str,
        ttl_hours: int,
    ) -> IssuedToken:
        plain_token = new_token(24)
        expires_at = now_utc() + timedelta(hours=max(ttl_hours, 1))
        record_id = self.repo.create_invitation(
            client_id=client_id,
            email=email.lower().strip(),
            role_code=role_code,
            invited_by_user_id=invited_by_user_id,
            token_hash=hash_token(plain_token),
            expires_at=expires_at,
        )
        return IssuedToken(record_id=record_id, plain_token=plain_token, expires_at=expires_at)

    def accept_invitation(self, token: str, name: str, password: str) -> AuthenticatedUser | None:
        record = self.repo.get_invitation_by_token_hash(hash_token(token))
        if record is None:
            return None
        if (
            record.accepted_at is not None
            or record.status != "pending"
            or ensure_utc(record.expires_at) < now_utc()
        ):
            return None

        accepted_at = now_utc()
        password_hash = hash_password(password)
        existing_user = self.repo.get_user_by_client_email(record.client_id, record.email)
        if existing_user is None:
            user = self.repo.create_user(
                client_id=record.client_id,
                name=name.strip(),
                email=record.email,
                password_hash=password_hash,
                role_code=record.role_code,
                invited_at=accepted_at,
            )
        else:
            self.repo.ensure_user_role(existing_user.user_id, record.role_code)
            user = self.repo.activate_invited_user(
                client_id=record.client_id,
                email=record.email,
                name=name.strip(),
                password_hash=password_hash,
                invited_at=accepted_at,
            )
            if user is None:
                return None
        self.repo.mark_invitation_accepted(record.invitation_id, accepted_at)
        return user
