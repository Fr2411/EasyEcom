from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.store.postgres_models import ClientModel, TenantSettingsModel


@dataclass
class BusinessProfilePatch:
    business_name: str | None = None
    display_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    currency_code: str | None = None
    timezone: str | None = None
    tax_registration_no: str | None = None


@dataclass
class OperationalPreferencesPatch:
    low_stock_threshold: int | None = None
    default_sales_note: str | None = None
    default_inventory_adjustment_reasons: list[str] | None = None
    default_payment_terms_days: int | None = None


@dataclass
class SequencePreferencesPatch:
    sales_prefix: str | None = None
    returns_prefix: str | None = None


class SettingsApiService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def _get_or_create_settings(self, session: Session, client_id: str) -> TenantSettingsModel:
        record = session.execute(
            select(TenantSettingsModel).where(TenantSettingsModel.client_id == client_id)
        ).scalar_one_or_none()
        if record is None:
            record = TenantSettingsModel(client_id=client_id, updated_at=now_iso())
            session.add(record)
            session.flush()
        return record

    @staticmethod
    def _clean_prefix(value: str) -> str:
        compact = "".join(ch for ch in value.upper().strip() if ch.isalnum())
        if not compact:
            raise ValueError("Prefix must include at least one alphanumeric character")
        if len(compact) > 12:
            raise ValueError("Prefix cannot exceed 12 characters")
        return compact

    @staticmethod
    def _parse_int(raw: str, fallback: int = 0) -> int:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _parse_reasons(raw: str) -> list[str]:
        if not raw.strip():
            return []
        return [part.strip() for part in raw.split("|") if part.strip()]

    def get_business_profile(self, *, client_id: str) -> dict[str, object] | None:
        with self.session_factory() as session:
            client = session.execute(
                select(ClientModel).where(ClientModel.client_id == client_id)
            ).scalar_one_or_none()
            if client is None:
                return None
            cfg = self._get_or_create_settings(session, client_id)
            session.commit()

        return {
            "client_id": client.client_id,
            "business_name": client.business_name,
            "display_name": client.owner_name,
            "phone": client.phone,
            "email": client.email,
            "address": client.address,
            "currency_code": client.currency_code,
            "timezone": cfg.timezone or "UTC",
            "tax_registration_no": cfg.tax_registration_no,
            "logo_upload_supported": False,
            "logo_upload_deferred_reason": "Tenant-scoped media storage is not implemented yet.",
        }

    def patch_business_profile(self, *, client_id: str, payload: BusinessProfilePatch) -> dict[str, object] | None:
        with self.session_factory() as session:
            client = session.execute(
                select(ClientModel).where(ClientModel.client_id == client_id)
            ).scalar_one_or_none()
            if client is None:
                return None
            cfg = self._get_or_create_settings(session, client_id)

            if payload.business_name is not None:
                client.business_name = payload.business_name.strip()
            if payload.display_name is not None:
                client.owner_name = payload.display_name.strip()
            if payload.phone is not None:
                client.phone = payload.phone.strip()
            if payload.email is not None:
                client.email = payload.email.strip().lower()
            if payload.address is not None:
                client.address = payload.address.strip()
            if payload.currency_code is not None:
                client.currency_code = payload.currency_code.strip().upper()

            if payload.timezone is not None:
                cfg.timezone = payload.timezone.strip()
            if payload.tax_registration_no is not None:
                cfg.tax_registration_no = payload.tax_registration_no.strip()
            cfg.updated_at = now_iso()
            session.commit()

        return self.get_business_profile(client_id=client_id)

    def get_preferences(self, *, client_id: str) -> dict[str, object] | None:
        with self.session_factory() as session:
            client = session.execute(
                select(ClientModel.client_id).where(ClientModel.client_id == client_id)
            ).scalar_one_or_none()
            if client is None:
                return None
            cfg = self._get_or_create_settings(session, client_id)
            session.commit()

        return {
            "low_stock_threshold": max(0, self._parse_int(cfg.low_stock_threshold, 5)),
            "default_sales_note": cfg.default_sales_note,
            "default_inventory_adjustment_reasons": self._parse_reasons(
                cfg.default_inventory_adjustment_reasons
            ),
            "default_payment_terms_days": max(0, self._parse_int(cfg.default_payment_terms_days, 0)),
            "active_usage": {
                "low_stock_threshold": False,
                "default_sales_note": False,
                "default_inventory_adjustment_reasons": False,
                "default_payment_terms_days": False,
            },
        }

    def patch_preferences(
        self, *, client_id: str, payload: OperationalPreferencesPatch
    ) -> dict[str, object] | None:
        with self.session_factory() as session:
            client = session.execute(
                select(ClientModel.client_id).where(ClientModel.client_id == client_id)
            ).scalar_one_or_none()
            if client is None:
                return None
            cfg = self._get_or_create_settings(session, client_id)

            if payload.low_stock_threshold is not None:
                if payload.low_stock_threshold < 0 or payload.low_stock_threshold > 999:
                    raise ValueError("low_stock_threshold must be between 0 and 999")
                cfg.low_stock_threshold = str(payload.low_stock_threshold)

            if payload.default_sales_note is not None:
                cfg.default_sales_note = payload.default_sales_note.strip()

            if payload.default_payment_terms_days is not None:
                if payload.default_payment_terms_days < 0 or payload.default_payment_terms_days > 365:
                    raise ValueError("default_payment_terms_days must be between 0 and 365")
                cfg.default_payment_terms_days = str(payload.default_payment_terms_days)

            if payload.default_inventory_adjustment_reasons is not None:
                compact = [item.strip() for item in payload.default_inventory_adjustment_reasons if item.strip()]
                cfg.default_inventory_adjustment_reasons = "|".join(compact[:20])

            cfg.updated_at = now_iso()
            session.commit()

        return self.get_preferences(client_id=client_id)

    def get_sequences(self, *, client_id: str) -> dict[str, object] | None:
        with self.session_factory() as session:
            client = session.execute(
                select(ClientModel.client_id).where(ClientModel.client_id == client_id)
            ).scalar_one_or_none()
            if client is None:
                return None
            cfg = self._get_or_create_settings(session, client_id)
            session.commit()

        return {
            "sales_prefix": cfg.sales_prefix or "SAL",
            "returns_prefix": cfg.returns_prefix or "RET",
            "active_usage": {
                "sales_prefix": False,
                "returns_prefix": False,
            },
        }

    def patch_sequences(self, *, client_id: str, payload: SequencePreferencesPatch) -> dict[str, object] | None:
        with self.session_factory() as session:
            client = session.execute(
                select(ClientModel.client_id).where(ClientModel.client_id == client_id)
            ).scalar_one_or_none()
            if client is None:
                return None
            cfg = self._get_or_create_settings(session, client_id)

            if payload.sales_prefix is not None:
                cfg.sales_prefix = self._clean_prefix(payload.sales_prefix)
            if payload.returns_prefix is not None:
                cfg.returns_prefix = self._clean_prefix(payload.returns_prefix)

            cfg.updated_at = now_iso()
            session.commit()

        return self.get_sequences(client_id=client_id)

    def get_tenant_context(self, *, client_id: str) -> dict[str, object] | None:
        with self.session_factory() as session:
            client = session.execute(
                select(ClientModel).where(ClientModel.client_id == client_id)
            ).scalar_one_or_none()
            if client is None:
                return None

        return {
            "client_id": client.client_id,
            "business_name": client.business_name,
            "status": client.status,
            "currency_code": client.currency_code,
        }
