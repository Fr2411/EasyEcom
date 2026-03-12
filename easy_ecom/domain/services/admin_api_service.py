from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.security import hash_password
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.store.postgres_models import ClientModel, UserModel, UserRoleModel

DEFAULT_ROLE_CODES = [
    "SUPER_ADMIN",
    "CLIENT_OWNER",
    "CLIENT_MANAGER",
    "CLIENT_EMPLOYEE",
    "FINANCE_ONLY",
]


@dataclass(frozen=True)
class AdminUserRecord:
    user_id: str
    client_id: str
    name: str
    email: str
    is_active: bool
    created_at: str
    roles: list[str]


@dataclass(frozen=True)
class AdminTenantRecord:
    client_id: str
    business_name: str
    owner_user: AdminUserRecord


class AdminApiService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def list_roles(self) -> list[str]:
        return list(DEFAULT_ROLE_CODES)

    def list_users_for_client(self, client_id: str) -> list[AdminUserRecord]:
        with self._session_factory() as session:
            users = (
                session.execute(select(UserModel).where(UserModel.client_id == client_id))
                .scalars()
                .all()
            )
            if not users:
                return []
            user_ids = [u.user_id for u in users]
            role_rows = (
                session.execute(select(UserRoleModel).where(UserRoleModel.user_id.in_(user_ids)))
                .scalars()
                .all()
            )
            role_map: dict[str, list[str]] = {}
            for row in role_rows:
                role_map.setdefault(row.user_id, []).append(row.role_code)
            return [
                AdminUserRecord(
                    user_id=user.user_id,
                    client_id=user.client_id,
                    name=user.name,
                    email=user.email,
                    is_active=str(user.is_active).strip().lower() == "true",
                    created_at=user.created_at,
                    roles=sorted(role_map.get(user.user_id, [])),
                )
                for user in users
            ]

    def get_user_for_client(self, client_id: str, user_id: str) -> AdminUserRecord | None:
        users = self.list_users_for_client(client_id)
        for user in users:
            if user.user_id == user_id:
                return user
        return None

    def _assert_client_exists(self, session: Session, client_id: str) -> None:
        existing = session.execute(
            select(ClientModel.client_id).where(ClientModel.client_id == client_id)
        ).scalar_one_or_none()
        if existing is None:
            raise ValueError("Client not found")

    def _assert_email_available(
        self, session: Session, email: str, exclude_user_id: str | None = None
    ) -> None:
        query = select(UserModel).where(UserModel.email == email)
        records = session.execute(query).scalars().all()
        for record in records:
            if exclude_user_id and record.user_id == exclude_user_id:
                continue
            raise ValueError("Email already in use")

    def create_user(
        self,
        *,
        client_id: str,
        name: str,
        email: str,
        password: str,
        role_codes: list[str],
        is_active: bool,
    ) -> AdminUserRecord:
        email_normalized = email.strip().lower()
        with self._session_factory() as session:
            self._assert_client_exists(session, client_id)
            self._assert_email_available(session, email_normalized)
            user_id = new_uuid()
            user = UserModel(
                user_id=user_id,
                client_id=client_id,
                name=name.strip(),
                email=email_normalized,
                password="",
                password_hash=hash_password(password),
                is_active="true" if is_active else "false",
                created_at=now_iso(),
            )
            session.add(user)
            for role_code in role_codes:
                session.add(UserRoleModel(user_id=user_id, role_code=role_code))
            session.commit()
        return self.get_user_for_client(client_id, user_id)  # type: ignore[return-value]

    def create_tenant_with_owner(
        self,
        *,
        business_name: str,
        owner_name: str,
        owner_email: str,
        owner_password: str,
        currency_code: str,
        owner_role_codes: list[str],
    ) -> AdminTenantRecord:
        cleaned_business_name = business_name.strip()
        cleaned_owner_name = owner_name.strip()
        cleaned_email = owner_email.strip().lower()
        cleaned_currency_code = currency_code.strip().upper()
        now = now_iso()

        with self._session_factory() as session:
            self._assert_email_available(session, cleaned_email)
            client_id = new_uuid()
            session.add(
                ClientModel(
                    client_id=client_id,
                    business_name=cleaned_business_name,
                    owner_name=cleaned_owner_name,
                    phone="",
                    email=cleaned_email,
                    address="",
                    currency_code=cleaned_currency_code,
                    currency_symbol="",
                    website_url="",
                    facebook_url="",
                    instagram_url="",
                    whatsapp_number="",
                    created_at=now,
                    status="active",
                    notes="",
                )
            )
            user_id = new_uuid()
            session.add(
                UserModel(
                    user_id=user_id,
                    client_id=client_id,
                    name=cleaned_owner_name,
                    email=cleaned_email,
                    password="",
                    password_hash=hash_password(owner_password),
                    is_active="true",
                    created_at=now,
                )
            )
            for role_code in owner_role_codes:
                session.add(UserRoleModel(user_id=user_id, role_code=role_code))
            session.commit()

        owner = self.get_user_for_client(client_id=client_id, user_id=user_id)
        if owner is None:
            raise ValueError("Owner user creation failed")
        return AdminTenantRecord(
            client_id=client_id,
            business_name=cleaned_business_name,
            owner_user=owner,
        )

    def update_user_profile(
        self,
        *,
        client_id: str,
        user_id: str,
        name: str | None,
        email: str | None,
        is_active: bool | None,
    ) -> AdminUserRecord | None:
        with self._session_factory() as session:
            user = session.execute(
                select(UserModel).where(
                    UserModel.client_id == client_id, UserModel.user_id == user_id
                )
            ).scalar_one_or_none()
            if user is None:
                return None

            if name is not None:
                user.name = name.strip()
            if email is not None:
                email_normalized = email.strip().lower()
                self._assert_email_available(session, email_normalized, exclude_user_id=user_id)
                user.email = email_normalized
            if is_active is not None:
                user.is_active = "true" if is_active else "false"

            session.commit()

        return self.get_user_for_client(client_id, user_id)

    def set_user_roles(
        self, *, client_id: str, user_id: str, role_codes: list[str]
    ) -> AdminUserRecord | None:
        with self._session_factory() as session:
            user = session.execute(
                select(UserModel).where(
                    UserModel.client_id == client_id, UserModel.user_id == user_id
                )
            ).scalar_one_or_none()
            if user is None:
                return None
            session.execute(delete(UserRoleModel).where(UserRoleModel.user_id == user_id))
            for role_code in role_codes:
                session.add(UserRoleModel(user_id=user_id, role_code=role_code))
            session.commit()
        return self.get_user_for_client(client_id, user_id)
