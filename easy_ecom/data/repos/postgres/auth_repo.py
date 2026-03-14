from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.ids import new_uuid
from easy_ecom.data.store.postgres_models import (
    PasswordResetTokenModel,
    UserInvitationModel,
    UserModel,
    UserRoleModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.auth_service import AuthUserRecord, InvitationRecord, PasswordResetRecord


@dataclass(frozen=True)
class PostgresUserRecord:
    user_id: str
    client_id: str
    name: str
    email: str
    password: str
    password_hash: str
    is_active: bool


class PostgresAuthRepo:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def get_user_by_email(self, email: str) -> AuthUserRecord | None:
        with self._session_factory() as session:
            record = session.execute(
                select(UserModel).where(UserModel.email == email.lower().strip())
            ).scalar_one_or_none()
            if record is None:
                return None
            return PostgresUserRecord(
                user_id=str(record.user_id),
                client_id=str(record.client_id),
                name=record.name,
                email=record.email,
                password=record.password or "",
                password_hash=(record.password_hash or ""),
                is_active=bool(record.is_active),
            )

    def get_roles_for_user(self, user_id: str) -> list[str]:
        with self._session_factory() as session:
            rows = session.execute(
                select(UserRoleModel.role_code).where(UserRoleModel.user_id == user_id)
            ).all()
            return [str(row[0]) for row in rows]

    def update_password_hash(self, user_id: str, password_hash: str) -> None:
        with self._session_factory() as session:
            user = session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            ).scalar_one_or_none()
            if user is None:
                return
            user.password_hash = password_hash
            user.password = ""
            session.commit()

    def touch_last_login(self, user_id: str, logged_in_at: datetime) -> None:
        with self._session_factory() as session:
            user = session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            ).scalar_one_or_none()
            if user is None:
                return
            user.last_login_at = logged_in_at
            session.commit()

    def create_password_reset_token(self, user_id: str, token_hash: str, expires_at: datetime) -> str:
        reset_token_id = new_uuid()
        with self._session_factory() as session:
            session.add(
                PasswordResetTokenModel(
                    reset_token_id=reset_token_id,
                    user_id=user_id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                )
            )
            session.commit()
        return reset_token_id

    def get_password_reset_by_token_hash(self, token_hash: str) -> PasswordResetRecord | None:
        with self._session_factory() as session:
            record = session.execute(
                select(PasswordResetTokenModel).where(PasswordResetTokenModel.token_hash == token_hash)
            ).scalar_one_or_none()
            if record is None:
                return None
            return PasswordResetRecord(
                reset_token_id=str(record.reset_token_id),
                user_id=str(record.user_id),
                expires_at=record.expires_at,
                consumed_at=record.consumed_at,
            )

    def mark_password_reset_consumed(self, reset_token_id: str, consumed_at: datetime) -> None:
        with self._session_factory() as session:
            record = session.execute(
                select(PasswordResetTokenModel).where(
                    PasswordResetTokenModel.reset_token_id == reset_token_id
                )
            ).scalar_one_or_none()
            if record is None:
                return
            record.consumed_at = consumed_at
            session.commit()

    def create_invitation(
        self,
        client_id: str,
        email: str,
        role_code: str,
        invited_by_user_id: str,
        token_hash: str,
        expires_at: datetime,
    ) -> str:
        invitation_id = new_uuid()
        with self._session_factory() as session:
            session.add(
                UserInvitationModel(
                    invitation_id=invitation_id,
                    client_id=client_id,
                    email=email,
                    role_code=role_code,
                    invited_by_user_id=invited_by_user_id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    status="pending",
                )
            )
            session.commit()
        return invitation_id

    def get_invitation_by_token_hash(self, token_hash: str) -> InvitationRecord | None:
        with self._session_factory() as session:
            record = session.execute(
                select(UserInvitationModel).where(UserInvitationModel.token_hash == token_hash)
            ).scalar_one_or_none()
            if record is None:
                return None
            return InvitationRecord(
                invitation_id=str(record.invitation_id),
                client_id=str(record.client_id),
                email=record.email,
                role_code=record.role_code,
                expires_at=record.expires_at,
                accepted_at=record.accepted_at,
                status=record.status,
            )

    def mark_invitation_accepted(self, invitation_id: str, accepted_at: datetime) -> None:
        with self._session_factory() as session:
            record = session.execute(
                select(UserInvitationModel).where(UserInvitationModel.invitation_id == invitation_id)
            ).scalar_one_or_none()
            if record is None:
                return
            record.accepted_at = accepted_at
            record.status = "accepted"
            session.commit()

    def create_user(
        self,
        *,
        client_id: str,
        name: str,
        email: str,
        password_hash: str,
        role_code: str,
        invited_at: datetime | None = None,
    ) -> AuthenticatedUser:
        user_id = new_uuid()
        normalized_email = email.lower().strip()
        with self._session_factory() as session:
            session.add(
                UserModel(
                    user_id=user_id,
                    client_id=client_id,
                    name=name,
                    email=normalized_email,
                    password="",
                    password_hash=password_hash,
                    is_active=True,
                    invited_at=invited_at,
                )
            )
            session.add(UserRoleModel(user_id=user_id, role_code=role_code))
            session.commit()

        return AuthenticatedUser(
            user_id=user_id,
            client_id=client_id,
            name=name,
            email=normalized_email,
            roles=[role_code],
        )
