from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from fastapi import Cookie, Depends, Request
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

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
from easy_ecom.domain.services.billing_service import BillingService
from easy_ecom.domain.services.commerce_service import (
    CatalogService,
    CustomersService,
    InventoryService,
    ReturnsService,
    SalesService,
)
from easy_ecom.domain.services.dashboard_service import DashboardAnalyticsService
from easy_ecom.domain.services.finance_posting_service import FinancePostingService
from easy_ecom.domain.services.overview_service import OverviewService
from easy_ecom.domain.services.settings_service import SettingsService
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
    billing_plan_code: str | None
    billing_status: str | None
    billing_access_state: str | None
    billing_grace_until: str | None


class RequestSessionFactory:
    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def __call__(self) -> Iterator[Session]:
        yield self._session


class ServiceContainer:
    def __init__(self, session: Session) -> None:
        session_factory = RequestSessionFactory(session)
        self._session = session
        self._session_factory = session_factory
        self.auth = AuthService(PostgresAuthRepo(session_factory))
        self.admin = AdminService(session_factory)
        self.billing = BillingService(session_factory)
        self.dashboard = DashboardAnalyticsService(session_factory)
        self.overview = OverviewService(session_factory)
        self._reports = None
        self.settings = SettingsService(session_factory)
        self.finance_posting = FinancePostingService()
        self.transaction = TransactionService(session_factory)
        self.catalog = CatalogService(session_factory)
        self.inventory = InventoryService(session_factory)
        self.customers = CustomersService(session_factory)
        self.sales = SalesService(session_factory)
        self.returns = ReturnsService(session_factory)

    @property
    def reports(self):
        if self._reports is None:
            from easy_ecom.domain.services.reports_service import ReportsService

            self._reports = ReportsService(self._session_factory)
        return self._reports


def _signer() -> SessionSigner:
    return SessionSigner(settings.session_secret)


def _ensure_runtime_state(request: Request) -> tuple[Engine, sessionmaker[Session]]:
    engine = getattr(request.app.state, "db_engine", None)
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if engine is None or session_factory is None:
        engine = build_runtime_engine(settings)
        session_factory = build_session_factory(engine)
        request.app.state.db_engine = engine
        request.app.state.db_session_factory = session_factory
    return engine, session_factory


def get_engine(request: Request) -> Engine:
    engine, _ = _ensure_runtime_state(request)
    return engine


def get_session_factory(request: Request) -> sessionmaker[Session]:
    _, session_factory = _ensure_runtime_state(request)
    return session_factory


def get_db_session(session_factory: sessionmaker[Session] = Depends(get_session_factory)) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_container(session: Session = Depends(get_db_session)) -> ServiceContainer:
    return ServiceContainer(session)


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
            "billing_plan_code": user.billing_plan_code,
            "billing_status": user.billing_status,
            "billing_access_state": user.billing_access_state,
            "billing_grace_until": user.billing_grace_until,
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
    raw_billing_plan_code = payload.get("billing_plan_code")
    raw_billing_status = payload.get("billing_status")
    raw_billing_access_state = payload.get("billing_access_state")
    raw_billing_grace_until = payload.get("billing_grace_until")
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
        billing_plan_code=str(raw_billing_plan_code).strip() if raw_billing_plan_code is not None else None,
        billing_status=str(raw_billing_status).strip() if raw_billing_status is not None else None,
        billing_access_state=str(raw_billing_access_state).strip() if raw_billing_access_state is not None else None,
        billing_grace_until=str(raw_billing_grace_until).strip() if raw_billing_grace_until is not None else None,
    )


def get_authenticated_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    request: Request = None,
    session: Session = Depends(get_db_session),
) -> AuthenticatedUser:
    session_user = _parse_session_user(session_token)
    billing_service = BillingService(RequestSessionFactory(session))
    billing_snapshot = billing_service.snapshot_for_request(
        session,
        client_id=session_user.client_id,
        roles=session_user.roles,
    )
    billing_user = AuthenticatedUser(
        user_id=session_user.user_id,
        client_id=session_user.client_id,
        roles=session_user.roles,
        allowed_pages=billing_snapshot.allowed_pages,
        email=session_user.email,
        name=session_user.name,
        business_name=session_user.business_name,
        billing_plan_code=billing_snapshot.plan_code,
        billing_status=billing_snapshot.billing_status,
        billing_access_state=billing_snapshot.billing_access_state,
        billing_grace_until=billing_snapshot.grace_until.isoformat() if billing_snapshot.grace_until else None,
    )
    if request is not None:
        billing_service.enforce_request_access(
            user=billing_user,
            request_method=request.method,
            request_path=request.url.path,
        )
        session.commit()
    return billing_user


def get_tenant_context(user: AuthenticatedUser = Depends(get_authenticated_user)) -> TenantContext:
    return TenantContext(user_id=user.user_id, client_id=user.client_id, roles=tuple(user.roles))


def require_page_access(user: AuthenticatedUser, page: str) -> None:
    if not can_access_page(user.roles, page, allowed_pages=user.allowed_pages):
        raise ApiException(
            status_code=403,
            code="ACCESS_DENIED",
            message=f"Access denied for {page}",
        )


def require_module_access(page: str) -> Callable[[AuthenticatedUser], None]:
    def _dependency(user: AuthenticatedUser = Depends(get_authenticated_user)) -> None:
        require_page_access(user, page)

    return _dependency
