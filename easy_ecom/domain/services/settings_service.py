from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.store.postgres_models import AuditLogModel, ClientModel, ClientSettingsModel
from easy_ecom.domain.models.auth import AuthenticatedUser


DEFAULT_LOW_STOCK_THRESHOLD = Decimal("5")


@dataclass(frozen=True)
class SettingsTenantContextRecord:
    client_id: str
    business_name: str
    status: str
    currency_code: str


@dataclass(frozen=True)
class SettingsProfileRecord:
    business_name: str
    contact_name: str
    owner_name: str
    email: str
    phone: str
    address: str
    website_url: str
    whatsapp_number: str
    timezone: str
    currency_code: str
    currency_symbol: str
    notes: str


@dataclass(frozen=True)
class SettingsDefaultsRecord:
    default_location_name: str
    low_stock_threshold: Decimal
    allow_backorder: bool
    require_discount_approval: bool


@dataclass(frozen=True)
class SettingsPrefixesRecord:
    sales_prefix: str
    purchases_prefix: str
    returns_prefix: str


@dataclass(frozen=True)
class SettingsWorkspaceRecord:
    tenant_context: SettingsTenantContextRecord
    profile: SettingsProfileRecord
    defaults: SettingsDefaultsRecord
    prefixes: SettingsPrefixesRecord


class SettingsService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_workspace(self, user: AuthenticatedUser) -> SettingsWorkspaceRecord:
        with self._session_factory() as session:
            client = self._get_client(session, user.client_id)
            client_settings = self._get_or_create_client_settings(session, user.client_id)
            session.commit()
            session.refresh(client_settings)
            return self._build_workspace(client, client_settings)

    def update_workspace(
        self,
        user: AuthenticatedUser,
        *,
        request_id: str | None,
        profile: dict[str, Any],
        defaults: dict[str, Any],
        prefixes: dict[str, Any],
    ) -> SettingsWorkspaceRecord:
        with self._session_factory() as session:
            client = self._get_client(session, user.client_id)
            client_settings = self._get_or_create_client_settings(session, user.client_id)
            changed_fields: list[str] = []

            changed_fields.extend(
                self._apply_client_updates(
                    client,
                    profile=profile,
                )
            )
            changed_fields.extend(
                self._apply_settings_updates(
                    client_settings,
                    defaults=defaults,
                    prefixes=prefixes,
                )
            )

            if changed_fields:
                self._log_audit(
                    session,
                    client_id=user.client_id,
                    actor_user_id=user.user_id,
                    entity_type="client_settings",
                    entity_id=user.client_id,
                    action="settings_updated",
                    request_id=request_id,
                    metadata_json={"changed_fields": changed_fields},
                )

            session.commit()
            session.refresh(client)
            session.refresh(client_settings)
            return self._build_workspace(client, client_settings)

    def _get_client(self, session: Session, client_id: str) -> ClientModel:
        client = session.execute(
            select(ClientModel).where(ClientModel.client_id == client_id)
        ).scalar_one_or_none()
        if client is None:
            raise ValueError(f"Client {client_id} not found")
        return client

    def _get_or_create_client_settings(self, session: Session, client_id: str) -> ClientSettingsModel:
        client_settings = session.execute(
            select(ClientSettingsModel).where(ClientSettingsModel.client_id == client_id)
        ).scalar_one_or_none()
        if client_settings is not None:
            return client_settings

        client_settings = ClientSettingsModel(
            client_settings_id=new_uuid(),
            client_id=client_id,
            low_stock_threshold=DEFAULT_LOW_STOCK_THRESHOLD,
            allow_backorder=False,
            default_location_name="Main Warehouse",
            require_discount_approval=False,
            order_prefix="SO",
            purchase_prefix="PO",
            return_prefix="RT",
        )
        session.add(client_settings)
        session.flush()
        return client_settings

    def _build_workspace(self, client: ClientModel, client_settings: ClientSettingsModel) -> SettingsWorkspaceRecord:
        return SettingsWorkspaceRecord(
            tenant_context=SettingsTenantContextRecord(
                client_id=str(client.client_id),
                business_name=client.business_name,
                status=client.status,
                currency_code=client.currency_code,
            ),
            profile=SettingsProfileRecord(
                business_name=client.business_name,
                contact_name=client.contact_name,
                owner_name=client.owner_name,
                email=client.email,
                phone=client.phone,
                address=client.address,
                website_url=client.website_url,
                whatsapp_number=client.whatsapp_number,
                timezone=client.timezone,
                currency_code=client.currency_code,
                currency_symbol=client.currency_symbol,
                notes=client.notes,
            ),
            defaults=SettingsDefaultsRecord(
                default_location_name=client_settings.default_location_name,
                low_stock_threshold=client_settings.low_stock_threshold,
                allow_backorder=client_settings.allow_backorder,
                require_discount_approval=client_settings.require_discount_approval,
            ),
            prefixes=SettingsPrefixesRecord(
                sales_prefix=client_settings.order_prefix,
                purchases_prefix=client_settings.purchase_prefix,
                returns_prefix=client_settings.return_prefix,
            ),
        )

    def _apply_client_updates(self, client: ClientModel, *, profile: dict[str, Any]) -> list[str]:
        changed_fields: list[str] = []
        field_map = {
            "business_name": str(profile.get("business_name", "")).strip(),
            "contact_name": str(profile.get("contact_name", "")).strip(),
            "owner_name": str(profile.get("owner_name", "")).strip(),
            "email": str(profile.get("email", "")).strip().lower(),
            "phone": str(profile.get("phone", "")).strip(),
            "address": str(profile.get("address", "")).strip(),
            "website_url": str(profile.get("website_url", "")).strip(),
            "whatsapp_number": str(profile.get("whatsapp_number", "")).strip(),
            "timezone": str(profile.get("timezone", "")).strip(),
            "currency_code": str(profile.get("currency_code", "")).strip().upper(),
            "currency_symbol": str(profile.get("currency_symbol", "")).strip(),
            "notes": str(profile.get("notes", "")).strip(),
        }

        for field_name, next_value in field_map.items():
            if getattr(client, field_name) != next_value:
                setattr(client, field_name, next_value)
                changed_fields.append(field_name)
        return changed_fields

    def _apply_settings_updates(
        self,
        client_settings: ClientSettingsModel,
        *,
        defaults: dict[str, Any],
        prefixes: dict[str, Any],
    ) -> list[str]:
        changed_fields: list[str] = []

        default_location_name = str(defaults.get("default_location_name", "")).strip()
        low_stock_threshold = Decimal(str(defaults.get("low_stock_threshold")))
        allow_backorder = bool(defaults.get("allow_backorder"))
        require_discount_approval = bool(defaults.get("require_discount_approval"))
        sales_prefix = str(prefixes.get("sales_prefix", "")).strip().upper()
        purchases_prefix = str(prefixes.get("purchases_prefix", "")).strip().upper()
        returns_prefix = str(prefixes.get("returns_prefix", "")).strip().upper()

        update_map = {
            "default_location_name": default_location_name,
            "low_stock_threshold": low_stock_threshold,
            "allow_backorder": allow_backorder,
            "require_discount_approval": require_discount_approval,
            "order_prefix": sales_prefix,
            "purchase_prefix": purchases_prefix,
            "return_prefix": returns_prefix,
        }

        for field_name, next_value in update_map.items():
            if getattr(client_settings, field_name) != next_value:
                setattr(client_settings, field_name, next_value)
                changed_fields.append(field_name)
        return changed_fields

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
