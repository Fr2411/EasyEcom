from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Cookie, Depends

from easy_ecom.core.config import settings
from easy_ecom.core.errors import ApiException
from easy_ecom.core.rbac import can_access_page, default_page_names_for_roles, mandatory_page_names_for_roles
from easy_ecom.core.session import SessionSigner
from easy_ecom.core.tenancy import TenantContext
from easy_ecom.data.repos.postgres.auth_repo import PostgresAuthRepo
from easy_ecom.data.store.postgres_db import build_session_factory
from easy_ecom.data.store.runtime import build_runtime_engine
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.admin_service import AdminService
from easy_ecom.domain.services.auth_service import AuthService
from easy_ecom.domain.services.commerce_service import (
    CatalogService,
    InventoryService,
    ReturnsService,
    SalesService,
)
from easy_ecom.domain.services.dashboard_service import DashboardAnalyticsService
from easy_ecom.domain.services.overview_service import OverviewService
from easy_ecom.domain.services.reports_service import ReportsService
from easy_ecom.domain.services.sales_agent_service import SalesAgentService
from easy_ecom.domain.services.transaction_service import TransactionService


@dataclass(frozen=True)
class SessionUserPayload:
    user_id: str
    client_id: str
    roles: list[str]
    allowed_pages: list[str]
    email: str
    name: str
    business_name: str | None


class ServiceContainer:
    def __init__(self) -> None:
        engine = build_runtime_engine(settings)
        session_factory = build_session_factory(engine)
        self.auth = AuthService(PostgresAuthRepo(session_factory))
        self.admin = AdminService(session_factory)
        self.dashboard = DashboardAnalyticsService(session_factory)
        self.overview = OverviewService(session_factory)
        self.reports = ReportsService(session_factory)
        self.transaction = TransactionService(session_factory)
        self.catalog = CatalogService(session_factory)
        self.inventory = InventoryService(session_factory)
        self.sales = SalesService(session_factory)
        self.returns = ReturnsService(session_factory)
        self.sales_agent = SalesAgentService(session_factory)


def _signer() -> SessionSigner:
    return SessionSigner(settings.session_secret)


def get_container() -> ServiceContainer:
    return ServiceContainer()


def build_session_token(user: AuthenticatedUser) -> str:
    return _signer().dumps(
        {
            "user_id": user.user_id,
            "client_id": user.client_id,
            "roles": user.roles,
            "allowed_pages": user.allowed_pages,
            "email": user.email,
            "name": user.name,
            "business_name": user.business_name,
        }
    )


def _unauthorized() -> ApiException:
    return ApiException(
        status_code=401,
        code="UNAUTHORIZED",
        message="Unauthorized",
    )


def _parse_roles(raw_roles: Any) -> list[str] | None:
    if isinstance(raw_roles, str):
        roles = [role.strip() for role in raw_roles.split(",") if role.strip()]
        return roles or None
    if isinstance(raw_roles, list):
        roles = [str(role).strip() for role in raw_roles if str(role).strip()]
        return roles or None
    return None


def _parse_session_user(token: str | None) -> SessionUserPayload:
    if not token:
        raise _unauthorized()
    payload = _signer().loads(token)
    if not isinstance(payload, dict):
        raise _unauthorized()

    user_id = str(payload.get("user_id", "")).strip()
    client_id = str(payload.get("client_id", "")).strip()
    email = str(payload.get("email", "")).strip()
    name = str(payload.get("name", "")).strip()
    raw_business_name = payload.get("business_name")
    business_name = str(raw_business_name).strip() if raw_business_name is not None else None
    roles = _parse_roles(payload.get("roles"))
    allowed_pages = _parse_roles(payload.get("allowed_pages")) or []

    if not user_id or not client_id or not email or not roles:
        raise _unauthorized()

    if not allowed_pages:
        allowed_pages = list(default_page_names_for_roles(roles))
    else:
        allowed_pages = list(dict.fromkeys([*allowed_pages, *mandatory_page_names_for_roles(roles)]))

    return SessionUserPayload(
        user_id=user_id,
        client_id=client_id,
        roles=roles,
        allowed_pages=allowed_pages,
        email=email,
        name=name,
        business_name=business_name or None,
    )


def get_authenticated_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> AuthenticatedUser:
    session_user = _parse_session_user(session_token)
    return AuthenticatedUser(
        user_id=session_user.user_id,
        client_id=session_user.client_id,
        roles=session_user.roles,
        allowed_pages=session_user.allowed_pages,
        email=session_user.email,
        name=session_user.name,
        business_name=session_user.business_name,
    )


def get_tenant_context(user: AuthenticatedUser = Depends(get_authenticated_user)) -> TenantContext:
    return TenantContext(user_id=user.user_id, client_id=user.client_id, roles=tuple(user.roles))


def require_page_access(user: AuthenticatedUser, page: str) -> None:
    if not can_access_page(user.roles, page, allowed_pages=user.allowed_pages):
        raise ApiException(
            status_code=403,
            code="ACCESS_DENIED",
            message=f"Access denied for {page}",
        )
