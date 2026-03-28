from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.config import settings
from easy_ecom.core.errors import ApiException
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.rbac import (
    OVERRIDABLE_PAGE_CODES,
    TENANT_ROLE_CODES,
    default_page_codes_for_roles,
    effective_page_names,
    page_names_from_codes,
    pages_for_role,
)
from easy_ecom.core.security import hash_password
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.repos.postgres.code_factory import generate_unique_client_code, generate_unique_user_code
from easy_ecom.data.store.postgres_models import (
    AuditLogModel,
    ClientModel,
    ClientSettingsModel,
    LocationModel,
    RoleModel,
    UserModel,
    UserPageAccessOverrideModel,
    UserRoleModel,
)
from easy_ecom.data.store.schema import ROLES_SEED
from easy_ecom.domain.models.auth import AuthenticatedUser


_CURRENCY_SYMBOLS = {
    "USD": "$",
    "AED": "AED",
    "BDT": "Tk",
    "EUR": "EUR",
    "GBP": "GBP",
}


@dataclass(frozen=True)
class AdminRoleAccess:
    role_code: str
    role_name: str
    description: str
    allowed_pages: tuple[str, ...]


@dataclass(frozen=True)
class AdminAuditEntry:
    audit_log_id: str
    client_id: str | None
    entity_type: str
    entity_id: str
    action: str
    actor_user_id: str | None
    created_at: datetime
    metadata_json: dict[str, Any] | None


@dataclass(frozen=True)
class AdminClientRecord:
    client_id: str
    client_code: str
    business_name: str
    contact_name: str
    owner_name: str
    email: str
    phone: str
    address: str
    website_url: str
    facebook_url: str
    instagram_url: str
    whatsapp_number: str
    status: str
    notes: str
    timezone: str
    currency_code: str
    currency_symbol: str
    default_location_name: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AdminUserRecord:
    user_id: str
    user_code: str
    client_id: str
    client_code: str
    name: str
    email: str
    role_code: str
    role_name: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


@dataclass(frozen=True)
class AdminOnboardResult:
    client: AdminClientRecord
    users: list[AdminUserRecord]
    warnings: list[str]


@dataclass(frozen=True)
class AdminUserAccessOverrideRecord:
    page_code: str
    is_allowed: bool


@dataclass(frozen=True)
class AdminUserAccessRecord:
    user_id: str
    role_code: str
    default_pages: tuple[str, ...]
    effective_pages: tuple[str, ...]
    overrides: tuple[AdminUserAccessOverrideRecord, ...]


class AdminService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_clients(self, *, search: str | None = None, status: str | None = None) -> list[AdminClientRecord]:
        with self._session_factory() as session:
            stmt = select(ClientModel).where(ClientModel.client_id != settings.global_client_id)
            if status:
                stmt = stmt.where(ClientModel.status == status.strip().lower())

            if search and search.strip():
                needle = f"%{search.strip().lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(ClientModel.business_name).like(needle),
                        func.lower(ClientModel.slug).like(needle),
                        func.lower(ClientModel.contact_name).like(needle),
                        func.lower(ClientModel.owner_name).like(needle),
                        func.lower(ClientModel.email).like(needle),
                    )
                )

            clients = session.execute(stmt.order_by(ClientModel.created_at.desc())).scalars().all()
            return [self._build_client_record(session, client) for client in clients]

    def get_client(self, client_id: str) -> AdminClientRecord:
        with self._session_factory() as session:
            client = self._get_client(session, client_id)
            return self._build_client_record(session, client)

    def update_client(
        self,
        *,
        client_id: str,
        actor: AuthenticatedUser,
        request_id: str | None,
        business_name: str | None = None,
        contact_name: str | None = None,
        owner_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        website_url: str | None = None,
        facebook_url: str | None = None,
        instagram_url: str | None = None,
        whatsapp_number: str | None = None,
        notes: str | None = None,
        timezone: str | None = None,
        currency_code: str | None = None,
        currency_symbol: str | None = None,
        status: str | None = None,
        default_location_name: str | None = None,
    ) -> AdminClientRecord:
        with self._session_factory() as session:
            client = self._get_client(session, client_id)
            client_settings = session.execute(
                select(ClientSettingsModel).where(ClientSettingsModel.client_id == client_id)
            ).scalar_one_or_none()

            changed_fields: list[str] = []
            updated_at = now_utc()

            def _set_attr(target: Any, field_name: str, next_value: str | None) -> None:
                if next_value is None:
                    return
                value = next_value.strip()
                if getattr(target, field_name) != value:
                    setattr(target, field_name, value)
                    changed_fields.append(field_name)

            _set_attr(client, "business_name", business_name)
            _set_attr(client, "contact_name", contact_name)
            _set_attr(client, "owner_name", owner_name)
            if email is not None:
                next_email = self._normalize_email(email)
                if client.email != next_email:
                    client.email = next_email
                    changed_fields.append("email")
            _set_attr(client, "phone", phone)
            _set_attr(client, "address", address)
            _set_attr(client, "website_url", website_url)
            _set_attr(client, "facebook_url", facebook_url)
            _set_attr(client, "instagram_url", instagram_url)
            _set_attr(client, "whatsapp_number", whatsapp_number)
            _set_attr(client, "notes", notes)
            _set_attr(client, "timezone", timezone)

            if currency_code is not None:
                normalized_currency = currency_code.strip().upper() or "USD"
                if client.currency_code != normalized_currency:
                    client.currency_code = normalized_currency
                    changed_fields.append("currency_code")
                next_symbol = (currency_symbol or self._currency_symbol_for(normalized_currency)).strip() or normalized_currency
                if client.currency_symbol != next_symbol:
                    client.currency_symbol = next_symbol
                    changed_fields.append("currency_symbol")
            elif currency_symbol is not None:
                next_symbol = currency_symbol.strip() or client.currency_symbol
                if client.currency_symbol != next_symbol:
                    client.currency_symbol = next_symbol
                    changed_fields.append("currency_symbol")

            if status is not None:
                next_status = status.strip().lower() or client.status
                if next_status not in {"active", "inactive"}:
                    raise ApiException(
                        status_code=400,
                        code="INVALID_STATUS",
                        message="Client status must be active or inactive",
                    )
                if client.status != next_status:
                    client.status = next_status
                    changed_fields.append("status")

            if client_settings is not None and default_location_name is not None:
                next_location = default_location_name.strip() or "Main Warehouse"
                if client_settings.default_location_name != next_location:
                    client_settings.default_location_name = next_location
                    client_settings.updated_at = updated_at
                    changed_fields.append("default_location_name")

            if changed_fields:
                client.updated_at = updated_at
                self._log_audit(
                    session,
                    client_id=client.client_id,
                    actor_user_id=actor.user_id,
                    entity_type="client",
                    entity_id=client.client_id,
                    action="client_updated",
                    request_id=request_id,
                    metadata_json={"changed_fields": changed_fields},
                )
                session.commit()

            return self._build_client_record(session, client)

    def list_users(self, client_id: str) -> list[AdminUserRecord]:
        with self._session_factory() as session:
            client = self._get_client(session, client_id)
            role_names = self._role_name_map(session)
            return self._users_for_client(session, client, role_names)

    def add_user(
        self,
        *,
        client_id: str,
        actor: AuthenticatedUser,
        request_id: str | None,
        name: str,
        email: str,
        role_code: str,
        password: str,
    ) -> AdminUserRecord:
        normalized_role = self._require_tenant_role(role_code)
        normalized_email = self._normalize_email(email)
        normalized_name = self._normalize_name(name)
        validated_password = self._validate_password(password)

        with self._session_factory() as session:
            client = self._get_client(session, client_id)
            self._assert_emails_available(session, [normalized_email])

            user_record = self._create_client_user(
                session,
                client=client,
                name=normalized_name,
                email=normalized_email,
                role_code=normalized_role,
                password=validated_password,
            )

            self._log_audit(
                session,
                client_id=client.client_id,
                actor_user_id=actor.user_id,
                entity_type="user",
                entity_id=user_record.user_id,
                action="user_created",
                request_id=request_id,
                metadata_json={"email": normalized_email, "role_code": normalized_role},
            )
            self._log_audit(
                session,
                client_id=client.client_id,
                actor_user_id=actor.user_id,
                entity_type="user",
                entity_id=user_record.user_id,
                action="password_set_by_admin",
                request_id=request_id,
                metadata_json={"email": normalized_email},
            )
            session.commit()
            return user_record

    def update_user(
        self,
        *,
        user_id: str,
        actor: AuthenticatedUser,
        request_id: str | None,
        name: str | None = None,
        role_code: str | None = None,
        is_active: bool | None = None,
    ) -> AdminUserRecord:
        with self._session_factory() as session:
            user = self._get_user(session, user_id)
            client = self._get_client(session, user.client_id)
            current_role = self._user_role_code(session, user.user_id)
            if current_role is None:
                raise ApiException(
                    status_code=400,
                    code="ROLE_NOT_FOUND",
                    message="User is missing an assigned role",
                )

            changed_fields: list[str] = []
            if name is not None:
                normalized_name = self._normalize_name(name)
                if user.name != normalized_name:
                    user.name = normalized_name
                    changed_fields.append("name")

            next_role = current_role
            if role_code is not None:
                next_role = self._require_tenant_role(role_code)
                if next_role != current_role:
                    if current_role == "CLIENT_OWNER" and next_role != "CLIENT_OWNER":
                        self._ensure_another_owner_exists(session, user.client_id, exclude_user_id=user.user_id)
                    session.execute(delete(UserRoleModel).where(UserRoleModel.user_id == user.user_id))
                    session.add(UserRoleModel(user_id=user.user_id, role_code=next_role))
                    changed_fields.append("role_code")

            if is_active is not None and user.is_active != is_active:
                if user.is_active and not is_active and current_role == "CLIENT_OWNER":
                    self._ensure_another_owner_exists(session, user.client_id, exclude_user_id=user.user_id)
                user.is_active = is_active
                changed_fields.append("is_active")

            if changed_fields:
                user.updated_at = now_utc()
                self._log_audit(
                    session,
                    client_id=user.client_id,
                    actor_user_id=actor.user_id,
                    entity_type="user",
                    entity_id=user.user_id,
                    action="user_updated",
                    request_id=request_id,
                    metadata_json={"changed_fields": changed_fields},
                )
                session.commit()

            role_names = self._role_name_map(session)
            return self._user_record_from_model(
                user=user,
                client_code=client.slug,
                role_code=next_role,
                role_names=role_names,
            )

    def set_user_password(
        self,
        *,
        user_id: str,
        actor: AuthenticatedUser,
        request_id: str | None,
        password: str,
    ) -> AdminUserRecord:
        validated_password = self._validate_password(password)
        with self._session_factory() as session:
            user = self._get_user(session, user_id)
            client = self._get_client(session, user.client_id)
            role_code = self._user_role_code(session, user.user_id)
            if role_code is None:
                raise ApiException(
                    status_code=400,
                    code="ROLE_NOT_FOUND",
                    message="User is missing an assigned role",
                )

            activated = not user.is_active and not user.password_hash and not user.password
            user.password = ""
            user.password_hash = hash_password(validated_password)
            if activated:
                user.is_active = True
            user.invited_at = None
            user.updated_at = now_utc()

            self._log_audit(
                session,
                client_id=user.client_id,
                actor_user_id=actor.user_id,
                entity_type="user",
                entity_id=user.user_id,
                action="password_set_by_admin",
                request_id=request_id,
                metadata_json={"activated": activated},
            )
            session.commit()

            role_names = self._role_name_map(session)
            return self._user_record_from_model(
                user=user,
                client_code=client.slug,
                role_code=role_code,
                role_names=role_names,
            )

    def get_user_access(self, user_id: str) -> AdminUserAccessRecord:
        with self._session_factory() as session:
            user = self._get_user(session, user_id)
            role_code = self._user_role_code(session, user.user_id)
            if role_code is None:
                raise ApiException(
                    status_code=400,
                    code="ROLE_NOT_FOUND",
                    message="User is missing an assigned role",
                )
            return self._build_user_access_record(session, user_id=str(user.user_id), role_code=role_code)

    def update_user_access(
        self,
        *,
        user_id: str,
        actor: AuthenticatedUser,
        request_id: str | None,
        overrides: list[dict[str, Any]],
    ) -> AdminUserAccessRecord:
        with self._session_factory() as session:
            user = self._get_user(session, user_id)
            role_code = self._user_role_code(session, user.user_id)
            if role_code is None:
                raise ApiException(
                    status_code=400,
                    code="ROLE_NOT_FOUND",
                    message="User is missing an assigned role",
                )

            next_overrides = self._normalize_access_overrides(overrides)
            current_rows = session.execute(
                select(UserPageAccessOverrideModel).where(UserPageAccessOverrideModel.user_id == user.user_id)
            ).scalars().all()
            current_map = {row.page_code: bool(row.is_allowed) for row in current_rows}
            next_map = {item.page_code: item.is_allowed for item in next_overrides}

            if current_map != next_map:
                session.execute(
                    delete(UserPageAccessOverrideModel).where(UserPageAccessOverrideModel.user_id == user.user_id)
                )
                timestamp = now_utc()
                for item in next_overrides:
                    session.add(
                        UserPageAccessOverrideModel(
                            override_id=new_uuid(),
                            user_id=user.user_id,
                            page_code=item.page_code,
                            is_allowed=item.is_allowed,
                            created_at=timestamp,
                            updated_at=timestamp,
                        )
                    )
                self._log_audit(
                    session,
                    client_id=user.client_id,
                    actor_user_id=actor.user_id,
                    entity_type="user_access",
                    entity_id=user.user_id,
                    action="user_access_updated",
                    request_id=request_id,
                    metadata_json={
                        "overrides": [
                            {"page_code": item.page_code, "is_allowed": item.is_allowed}
                            for item in next_overrides
                        ]
                    },
                )
                session.commit()

            return self._build_user_access_record(session, user_id=str(user.user_id), role_code=role_code)

    def roles(self) -> list[AdminRoleAccess]:
        role_map = {item["role_code"]: item for item in ROLES_SEED}
        ordered_codes = ["SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_STAFF", "FINANCE_STAFF"]
        return [
            AdminRoleAccess(
                role_code=role_code,
                role_name=role_map[role_code]["role_name"],
                description=role_map[role_code]["description"],
                allowed_pages=pages_for_role(role_code),
            )
            for role_code in ordered_codes
        ]

    def audit(self, *, client_id: str | None = None, limit: int = 20) -> list[AdminAuditEntry]:
        safe_limit = max(1, min(limit, 100))
        with self._session_factory() as session:
            stmt = select(AuditLogModel)
            if client_id:
                self._get_client(session, client_id)
                stmt = stmt.where(AuditLogModel.client_id == client_id)
            else:
                stmt = stmt.where(AuditLogModel.client_id != settings.global_client_id)
            rows = session.execute(stmt.order_by(AuditLogModel.created_at.desc()).limit(safe_limit)).scalars().all()
            return [
                AdminAuditEntry(
                    audit_log_id=str(row.audit_log_id),
                    client_id=str(row.client_id) if row.client_id else None,
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    action=row.action,
                    actor_user_id=str(row.actor_user_id) if row.actor_user_id else None,
                    created_at=row.created_at,
                    metadata_json=row.metadata_json,
                )
                for row in rows
            ]

    def onboard_client(
        self,
        *,
        actor: AuthenticatedUser,
        request_id: str | None,
        business_name: str,
        contact_name: str,
        primary_email: str,
        primary_phone: str,
        owner_name: str,
        owner_email: str,
        owner_password: str,
        address: str = "",
        website_url: str = "",
        facebook_url: str = "",
        instagram_url: str = "",
        whatsapp_number: str = "",
        notes: str = "",
        timezone: str | None = None,
        currency_code: str | None = None,
        currency_symbol: str | None = None,
        default_location_name: str | None = None,
        additional_users: list[dict[str, str]] | None = None,
    ) -> AdminOnboardResult:
        return self._provision_client(
            actor_user_id=actor.user_id,
            request_id=request_id,
            business_name=business_name,
            contact_name=contact_name,
            primary_email=primary_email,
            primary_phone=primary_phone,
            owner_name=owner_name,
            owner_email=owner_email,
            owner_password=owner_password,
            address=address,
            website_url=website_url,
            facebook_url=facebook_url,
            instagram_url=instagram_url,
            whatsapp_number=whatsapp_number,
            notes=notes,
            timezone=timezone,
            currency_code=currency_code,
            currency_symbol=currency_symbol,
            default_location_name=default_location_name,
            additional_users=additional_users,
        )

    def signup_client(
        self,
        *,
        request_id: str | None,
        business_name: str,
        owner_name: str,
        owner_email: str,
        owner_password: str,
        primary_phone: str,
    ) -> AdminOnboardResult:
        return self._provision_client(
            actor_user_id=None,
            request_id=request_id,
            business_name=business_name,
            contact_name=owner_name,
            primary_email=owner_email,
            primary_phone=primary_phone,
            owner_name=owner_name,
            owner_email=owner_email,
            owner_password=owner_password,
        )

    def _provision_client(
        self,
        *,
        actor_user_id: str | None,
        request_id: str | None,
        business_name: str,
        contact_name: str,
        primary_email: str,
        primary_phone: str,
        owner_name: str,
        owner_email: str,
        owner_password: str,
        address: str = "",
        website_url: str = "",
        facebook_url: str = "",
        instagram_url: str = "",
        whatsapp_number: str = "",
        notes: str = "",
        timezone: str | None = None,
        currency_code: str | None = None,
        currency_symbol: str | None = None,
        default_location_name: str | None = None,
        additional_users: list[dict[str, str]] | None = None,
    ) -> AdminOnboardResult:
        normalized_business_name = business_name.strip()
        normalized_contact_name = self._normalize_name(contact_name)
        normalized_primary_email = self._normalize_email(primary_email)
        normalized_primary_phone = primary_phone.strip()
        normalized_owner_name = self._normalize_name(owner_name)
        normalized_owner_email = self._normalize_email(owner_email)
        validated_owner_password = self._validate_password(owner_password)
        normalized_timezone = timezone.strip() if timezone and timezone.strip() else "UTC"
        normalized_currency_code = (currency_code or "USD").strip().upper() or "USD"
        normalized_currency_symbol = (currency_symbol or self._currency_symbol_for(normalized_currency_code)).strip() or normalized_currency_code
        normalized_default_location_name = default_location_name.strip() if default_location_name and default_location_name.strip() else "Main Warehouse"

        if not normalized_business_name:
            raise ApiException(
                status_code=400,
                code="BUSINESS_NAME_REQUIRED",
                message="Business name is required",
            )
        if not normalized_primary_phone:
            raise ApiException(
                status_code=400,
                code="PRIMARY_PHONE_REQUIRED",
                message="Primary phone is required",
            )

        extra_users = additional_users or []
        normalized_additional_users: list[dict[str, str]] = []
        for raw_user in extra_users:
            normalized_additional_users.append(
                {
                    "name": self._normalize_name(raw_user.get("name", "")),
                    "email": self._normalize_email(raw_user.get("email", "")),
                    "role_code": self._require_tenant_role(raw_user.get("role_code", "")),
                    "password": self._validate_password(raw_user.get("password", "")),
                }
            )

        intake_emails = [normalized_owner_email, *[item["email"] for item in normalized_additional_users]]
        with self._session_factory() as session:
            warnings = self._duplicate_warnings(
                session,
                business_name=normalized_business_name,
                email=normalized_primary_email,
                website_url=website_url.strip(),
                facebook_url=facebook_url.strip(),
                instagram_url=instagram_url.strip(),
            )
            self._assert_emails_available(session, intake_emails)

            client_code = generate_unique_client_code(session, normalized_business_name)
            timestamp = now_utc()
            client_id = new_uuid()
            client = ClientModel(
                client_id=client_id,
                slug=client_code,
                business_name=normalized_business_name,
                contact_name=normalized_contact_name,
                owner_name=normalized_owner_name,
                phone=normalized_primary_phone,
                email=normalized_primary_email,
                address=address.strip(),
                currency_code=normalized_currency_code,
                currency_symbol=normalized_currency_symbol,
                timezone=normalized_timezone,
                website_url=website_url.strip(),
                facebook_url=facebook_url.strip(),
                instagram_url=instagram_url.strip(),
                whatsapp_number=whatsapp_number.strip(),
                status="active",
                notes=notes.strip(),
                created_at=timestamp,
                updated_at=timestamp,
            )
            session.add(client)
            session.add(
                ClientSettingsModel(
                    client_settings_id=new_uuid(),
                    client_id=client_id,
                    default_location_name=normalized_default_location_name,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
            session.add(
                LocationModel(
                    location_id=new_uuid(),
                    client_id=client_id,
                    name=normalized_default_location_name,
                    code="MAIN",
                    is_default=True,
                    status="active",
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )

            created_users: list[AdminUserRecord] = [
                self._create_client_user(
                    session,
                    client=client,
                    name=normalized_owner_name,
                    email=normalized_owner_email,
                    role_code="CLIENT_OWNER",
                    password=validated_owner_password,
                    created_at=timestamp,
                )
            ]

            for user_payload in normalized_additional_users:
                created_users.append(
                    self._create_client_user(
                        session,
                        client=client,
                        name=user_payload["name"],
                        email=user_payload["email"],
                        role_code=user_payload["role_code"],
                        password=user_payload["password"],
                        created_at=timestamp,
                    )
                )

            session.flush()

            self._log_audit(
                session,
                client_id=client_id,
                actor_user_id=actor_user_id,
                entity_type="client",
                entity_id=client_id,
                action="client_created",
                request_id=request_id,
                metadata_json={"client_code": client_code},
            )
            for created_user in created_users:
                self._log_audit(
                    session,
                    client_id=client_id,
                    actor_user_id=actor_user_id,
                    entity_type="user",
                    entity_id=created_user.user_id,
                    action="user_created",
                    request_id=request_id,
                    metadata_json={"email": created_user.email, "role_code": created_user.role_code},
                )
                self._log_audit(
                    session,
                    client_id=client_id,
                    actor_user_id=actor_user_id,
                    entity_type="user",
                    entity_id=created_user.user_id,
                    action="password_set_by_admin",
                    request_id=request_id,
                    metadata_json={"email": created_user.email},
                )
            session.commit()

            return AdminOnboardResult(
                client=self._build_client_record(session, client),
                users=created_users,
                warnings=warnings,
            )

    def _build_client_record(self, session: Session, client: ClientModel) -> AdminClientRecord:
        client_settings = session.execute(
            select(ClientSettingsModel).where(ClientSettingsModel.client_id == client.client_id)
        ).scalar_one_or_none()
        return AdminClientRecord(
            client_id=str(client.client_id),
            client_code=client.slug,
            business_name=client.business_name,
            contact_name=client.contact_name,
            owner_name=client.owner_name,
            email=client.email,
            phone=client.phone,
            address=client.address,
            website_url=client.website_url,
            facebook_url=client.facebook_url,
            instagram_url=client.instagram_url,
            whatsapp_number=client.whatsapp_number,
            status=client.status,
            notes=client.notes,
            timezone=client.timezone,
            currency_code=client.currency_code,
            currency_symbol=client.currency_symbol,
            default_location_name=client_settings.default_location_name if client_settings else "Main Warehouse",
            created_at=client.created_at,
            updated_at=client.updated_at,
        )

    def _create_client_user(
        self,
        session: Session,
        *,
        client: ClientModel,
        name: str,
        email: str,
        role_code: str,
        password: str,
        created_at: datetime | None = None,
    ) -> AdminUserRecord:
        timestamp = created_at or now_utc()
        user_id = new_uuid()
        user_code = generate_unique_user_code(session, client.slug, role_code, name)
        session.add(
            UserModel(
                user_id=user_id,
                user_code=user_code,
                client_id=client.client_id,
                name=name,
                email=email,
                password="",
                password_hash=hash_password(password),
                is_active=True,
                invited_at=None,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        session.add(UserRoleModel(user_id=user_id, role_code=role_code))
        role_names = self._role_name_map(session)
        return AdminUserRecord(
            user_id=user_id,
            user_code=user_code,
            client_id=str(client.client_id),
            client_code=client.slug,
            name=name,
            email=email,
            role_code=role_code,
            role_name=role_names.get(role_code, role_code),
            is_active=True,
            created_at=timestamp,
            last_login_at=None,
        )

    def _build_user_access_record(self, session: Session, *, user_id: str, role_code: str) -> AdminUserAccessRecord:
        override_rows = session.execute(
            select(UserPageAccessOverrideModel)
            .where(UserPageAccessOverrideModel.user_id == user_id)
            .order_by(UserPageAccessOverrideModel.page_code.asc())
        ).scalars().all()
        overrides = tuple(
            AdminUserAccessOverrideRecord(page_code=row.page_code, is_allowed=bool(row.is_allowed))
            for row in override_rows
        )
        granted_page_codes = [row.page_code for row in override_rows if row.is_allowed]
        revoked_page_codes = [row.page_code for row in override_rows if not row.is_allowed]
        default_pages = default_page_codes_for_roles([role_code])
        effective_names = effective_page_names([role_code], granted_page_codes, revoked_page_codes)
        effective_page_codes = tuple(
            page_code
            for page_code in OVERRIDABLE_PAGE_CODES
            if page_names_from_codes([page_code])[0] in set(effective_names)
        )
        return AdminUserAccessRecord(
            user_id=user_id,
            role_code=role_code,
            default_pages=default_pages,
            effective_pages=effective_page_codes,
            overrides=overrides,
        )

    def _normalize_access_overrides(self, overrides: list[dict[str, Any]]) -> list[AdminUserAccessOverrideRecord]:
        normalized: list[AdminUserAccessOverrideRecord] = []
        seen_codes: set[str] = set()
        for raw in overrides:
            page_code = str(raw.get("page_code", "")).strip().upper()
            if page_code not in OVERRIDABLE_PAGE_CODES:
                raise ApiException(
                    status_code=400,
                    code="INVALID_PAGE_OVERRIDE",
                    message="Page override must target a supported core page",
                )
            if page_code in seen_codes:
                raise ApiException(
                    status_code=400,
                    code="DUPLICATE_PAGE_OVERRIDE",
                    message="Duplicate page overrides are not allowed in the same request",
                )
            seen_codes.add(page_code)
            normalized.append(
                AdminUserAccessOverrideRecord(page_code=page_code, is_allowed=bool(raw.get("is_allowed")))
            )
        return sorted(normalized, key=lambda item: item.page_code)

    def _duplicate_warnings(
        self,
        session: Session,
        *,
        business_name: str,
        email: str,
        website_url: str,
        facebook_url: str,
        instagram_url: str,
    ) -> list[str]:
        conditions = [func.lower(ClientModel.business_name) == business_name.lower()]
        if email:
            conditions.append(func.lower(ClientModel.email) == email.lower())
        if website_url:
            conditions.append(func.lower(ClientModel.website_url) == website_url.lower())
        if facebook_url:
            conditions.append(func.lower(ClientModel.facebook_url) == facebook_url.lower())
        if instagram_url:
            conditions.append(func.lower(ClientModel.instagram_url) == instagram_url.lower())

        rows = session.execute(
            select(ClientModel)
            .where(ClientModel.client_id != settings.global_client_id)
            .where(or_(*conditions))
            .order_by(ClientModel.created_at.desc())
        ).scalars().all()

        warnings: list[str] = []
        for client in rows:
            reasons: list[str] = []
            if client.business_name.lower() == business_name.lower():
                reasons.append("business name")
            if email and client.email.lower() == email.lower():
                reasons.append("primary email")
            if website_url and client.website_url.lower() == website_url.lower():
                reasons.append("website")
            if facebook_url and client.facebook_url.lower() == facebook_url.lower():
                reasons.append("Facebook")
            if instagram_url and client.instagram_url.lower() == instagram_url.lower():
                reasons.append("Instagram")
            warnings.append(
                f"Potential duplicate client: {client.business_name} ({client.slug}) matched on {', '.join(reasons)}."
            )
        return warnings

    def _assert_emails_available(self, session: Session, emails: list[str]) -> None:
        normalized = [self._normalize_email(email) for email in emails]
        duplicates = sorted(email for email, count in Counter(normalized).items() if count > 1)
        if duplicates:
            raise ApiException(
                status_code=400,
                code="DUPLICATE_EMAILS",
                message="Duplicate user emails are not allowed in the same request",
                details={"emails": duplicates},
            )

        existing_emails = session.execute(
            select(UserModel.email).where(UserModel.email.in_(normalized))
        ).scalars().all()
        if existing_emails:
            raise ApiException(
                status_code=409,
                code="USER_EMAIL_ALREADY_EXISTS",
                message="One or more user emails already exist",
                details={"emails": sorted({email for email in existing_emails})},
            )

    def _users_for_client(
        self,
        session: Session,
        client: ClientModel,
        role_names: dict[str, str],
    ) -> list[AdminUserRecord]:
        users = session.execute(
            select(UserModel)
            .where(UserModel.client_id == client.client_id)
            .order_by(UserModel.created_at.desc(), UserModel.email.asc())
        ).scalars().all()
        if not users:
            return []

        user_ids = [str(user.user_id) for user in users]
        role_rows = session.execute(
            select(UserRoleModel.user_id, UserRoleModel.role_code).where(UserRoleModel.user_id.in_(user_ids))
        ).all()
        role_map = {str(row_user_id): str(row_role_code) for row_user_id, row_role_code in role_rows}
        return [
            self._user_record_from_model(
                user=user,
                client_code=client.slug,
                role_code=role_map.get(str(user.user_id), ""),
                role_names=role_names,
            )
            for user in users
        ]

    def _user_record_from_model(
        self,
        *,
        user: UserModel,
        client_code: str,
        role_code: str,
        role_names: dict[str, str],
    ) -> AdminUserRecord:
        return AdminUserRecord(
            user_id=str(user.user_id),
            user_code=user.user_code,
            client_id=str(user.client_id),
            client_code=client_code,
            name=user.name,
            email=user.email,
            role_code=role_code,
            role_name=role_names.get(role_code, role_code),
            is_active=bool(user.is_active),
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )

    def _ensure_another_owner_exists(self, session: Session, client_id: str, *, exclude_user_id: str) -> None:
        count = session.execute(
            select(func.count())
            .select_from(UserModel)
            .join(UserRoleModel, UserRoleModel.user_id == UserModel.user_id)
            .where(
                UserModel.client_id == client_id,
                UserModel.user_id != exclude_user_id,
                UserModel.is_active.is_(True),
                UserRoleModel.role_code == "CLIENT_OWNER",
            )
        ).scalar_one()
        if int(count or 0) < 1:
            raise ApiException(
                status_code=400,
                code="LAST_OWNER_PROTECTION",
                message="Each client must keep at least one active client owner",
            )

    def _get_client(self, session: Session, client_id: str) -> ClientModel:
        client = session.execute(
            select(ClientModel).where(
                ClientModel.client_id == client_id,
                ClientModel.client_id != settings.global_client_id,
            )
        ).scalar_one_or_none()
        if client is None:
            raise ApiException(
                status_code=404,
                code="CLIENT_NOT_FOUND",
                message="Client was not found",
            )
        return client

    def _get_user(self, session: Session, user_id: str) -> UserModel:
        user = session.execute(
            select(UserModel)
            .where(
                UserModel.user_id == user_id,
                UserModel.client_id != settings.global_client_id,
            )
        ).scalar_one_or_none()
        if user is None:
            raise ApiException(
                status_code=404,
                code="USER_NOT_FOUND",
                message="User was not found",
            )
        return user

    def _user_role_code(self, session: Session, user_id: str) -> str | None:
        return session.execute(
            select(UserRoleModel.role_code)
            .where(UserRoleModel.user_id == user_id)
            .order_by(UserRoleModel.role_code.asc())
        ).scalar_one_or_none()

    def _role_name_map(self, session: Session) -> dict[str, str]:
        rows = session.execute(select(RoleModel.role_code, RoleModel.role_name)).all()
        return {str(role_code): str(role_name) for role_code, role_name in rows}

    def _require_tenant_role(self, role_code: str) -> str:
        normalized = role_code.strip().upper()
        if normalized not in TENANT_ROLE_CODES:
            raise ApiException(
                status_code=400,
                code="INVALID_ROLE",
                message="Role must be one of CLIENT_OWNER, CLIENT_STAFF, or FINANCE_STAFF",
            )
        return normalized

    def _normalize_email(self, email: str) -> str:
        normalized = email.strip().lower()
        if not normalized:
            raise ApiException(
                status_code=400,
                code="EMAIL_REQUIRED",
                message="Email is required",
            )
        return normalized

    def _normalize_name(self, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ApiException(
                status_code=400,
                code="NAME_REQUIRED",
                message="Name must contain at least two characters",
            )
        return normalized

    def _validate_password(self, password: str) -> str:
        if len(password) < 6:
            raise ApiException(
                status_code=400,
                code="PASSWORD_TOO_SHORT",
                message="Password must contain at least six characters",
            )
        return password

    def _currency_symbol_for(self, currency_code: str) -> str:
        return _CURRENCY_SYMBOLS.get(currency_code.upper(), currency_code.upper())

    def _log_audit(
        self,
        session: Session,
        *,
        client_id: str | None,
        actor_user_id: str | None,
        entity_type: str,
        entity_id: str,
        action: str,
        request_id: str | None,
        metadata_json: dict[str, Any] | None,
    ) -> None:
        session.add(
            AuditLogModel(
                audit_log_id=new_uuid(),
                client_id=client_id,
                actor_user_id=actor_user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                request_id=request_id,
                metadata_json=metadata_json,
                created_at=now_utc(),
            )
        )
