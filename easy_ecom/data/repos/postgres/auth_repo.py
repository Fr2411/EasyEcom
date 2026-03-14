from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.data.store.postgres_models import (
    UserModel,
    UserRoleModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.auth_service import AuthUserRecord


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

    def _record_from_model(self, record: UserModel) -> AuthUserRecord:
        return PostgresUserRecord(
            user_id=str(record.user_id),
            client_id=str(record.client_id),
            name=record.name,
            email=record.email,
            password=record.password or "",
            password_hash=(record.password_hash or ""),
            is_active=bool(record.is_active),
        )

    def get_user_by_email(self, email: str) -> AuthUserRecord | None:
        with self._session_factory() as session:
            record = session.execute(
                select(UserModel).where(UserModel.email == email.lower().strip())
            ).scalar_one_or_none()
            if record is None:
                return None
            return self._record_from_model(record)

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
