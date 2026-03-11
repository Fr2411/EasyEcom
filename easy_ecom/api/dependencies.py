from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Cookie, Depends, HTTPException

from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.core.session import SessionSigner
from easy_ecom.data.repos.csv.audit_repo import AuditRepo
from easy_ecom.data.repos.csv.auth_repo import CsvAuthRepo
from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.customers_repo import CustomersRepo
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import (
    InvoicesRepo,
    PaymentsRepo,
    SalesOrderItemsRepo,
    SalesOrdersRepo,
    ShipmentsRepo,
)
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.repos.csv.users_repo import RolesRepo, UserRolesRepo, UsersRepo
from easy_ecom.data.repos.postgres.auth_repo import PostgresAuthRepo
from easy_ecom.data.repos.postgres.customers_repo import CustomersPostgresRepo
from easy_ecom.data.store.postgres_db import build_postgres_engine, build_session_factory
from easy_ecom.data.store.runtime import build_runtime_store
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.auth_service import AuthService
from easy_ecom.domain.services.admin_api_service import AdminApiService
from easy_ecom.domain.services.catalog_stock_service import CatalogStockService
from easy_ecom.domain.services.dashboard_service import DashboardService
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.finance_api_service import FinanceApiService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService
from easy_ecom.domain.services.sales_service import SalesService
from easy_ecom.domain.services.sales_api_service import SalesApiService
from easy_ecom.domain.services.returns_api_service import ReturnsApiService
from easy_ecom.domain.services.customer_service import CustomerService
from easy_ecom.domain.services.settings_api_service import SettingsApiService
from easy_ecom.domain.services.purchases_api_service import PurchasesApiService
from easy_ecom.domain.services.reports_api_service import ReportsApiService
from easy_ecom.domain.services.ai_context_service import AiContextService
from easy_ecom.domain.services.integrations_service import IntegrationsService
from easy_ecom.domain.services.ai_review_service import AiReviewService
from easy_ecom.domain.services.user_service import UserService


@dataclass
class RequestUser:
    user_id: str
    client_id: str
    roles: list[str]


@dataclass(frozen=True)
class SessionUserPayload:
    user_id: str
    client_id: str
    roles: list[str]
    email: str
    name: str


class ServiceContainer:
    def __init__(self) -> None:
        self.store = build_runtime_store(settings)
        for table, columns in TABLE_SCHEMAS.items():
            self.store.ensure_table(table, columns)

        users_repo = UsersRepo(self.store)
        user_roles_repo = UserRolesRepo(self.store)

        self.users = UserService(users_repo, RolesRepo(self.store), user_roles_repo)
        self.sequence = SequenceService(SequencesRepo(self.store))

        if settings.storage_backend == "csv":
            self.auth = AuthService(CsvAuthRepo(users_repo, user_roles_repo))
        else:
            engine = build_postgres_engine(settings)
            self.auth = AuthService(PostgresAuthRepo(build_session_factory(engine)))

        products_repo = ProductsRepo(self.store)
        variants_repo = ProductVariantsRepo(self.store)
        inventory_repo = InventoryTxnRepo(self.store)
        self.products = ProductService(products_repo, variants_repo)
        self.inventory = InventoryService(
            inventory_repo,
            self.sequence,
            products_repo=products_repo,
            variants_repo=variants_repo,
        )
        self.catalog_stock = CatalogStockService(self.products, self.inventory)
        self.dashboard = DashboardService(
            inventory_repo,
            LedgerRepo(self.store),
            SalesOrdersRepo(self.store),
            InvoicesRepo(self.store),
            SalesOrderItemsRepo(self.store),
            products_repo,
            variants_repo,
            ClientsRepo(self.store),
            PaymentsRepo(self.store),
        )
        self.sales_mvp = None
        self.finance_mvp = None
        self.returns_mvp = None
        self.admin = None
        self.settings_mvp = None
        self.purchases_mvp = None
        self.reports_mvp = None
        self.ai_context = None
        self.integrations = None
        self.ai_review = None
        if settings.storage_backend == "postgres":
            engine = build_postgres_engine(settings)
            session_factory = build_session_factory(engine)
            self.customers = CustomerService(CustomersPostgresRepo(session_factory))
            self.sales_mvp = SalesApiService(session_factory)
            self.finance_mvp = FinanceApiService(session_factory)
            self.returns_mvp = ReturnsApiService(session_factory)
            self.admin = AdminApiService(session_factory)
            self.settings_mvp = SettingsApiService(session_factory)
            self.purchases_mvp = PurchasesApiService(session_factory)
            self.reports_mvp = ReportsApiService(session_factory)
            self.ai_context = AiContextService(session_factory)
            self.integrations = IntegrationsService(session_factory, ai_context_service=self.ai_context)
            self.ai_review = AiReviewService(session_factory, ai_context_service=self.ai_context, integrations_service=self.integrations)
        else:
            self.customers = CustomerService(CustomersRepo(self.store))

        self.sales = SalesService(
            SalesOrdersRepo(self.store),
            SalesOrderItemsRepo(self.store),
            InvoicesRepo(self.store),
            ShipmentsRepo(self.store),
            PaymentsRepo(self.store),
            self.inventory,
            self.sequence,
            FinanceService(LedgerRepo(self.store), inventory_repo),
            products_repo,
            CustomersRepo(self.store),
            AuditRepo(self.store),
            variants_repo,
        )


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
            "email": user.email,
            "name": user.name,
        }
    )


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Unauthorized")


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
    roles = _parse_roles(payload.get("roles"))

    if not user_id or not client_id or not email or not roles:
        raise _unauthorized()

    return SessionUserPayload(
        user_id=user_id,
        client_id=client_id,
        roles=roles,
        email=email,
        name=name,
    )


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> RequestUser:
    session_user = _parse_session_user(session_token)
    return RequestUser(
        user_id=session_user.user_id,
        client_id=session_user.client_id,
        roles=session_user.roles,
    )


def get_authenticated_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> AuthenticatedUser:
    session_user = _parse_session_user(session_token)
    return AuthenticatedUser(
        user_id=session_user.user_id,
        client_id=session_user.client_id,
        roles=session_user.roles,
        email=session_user.email,
        name=session_user.name,
    )


def require_page_access(user: RequestUser, page: str) -> None:
    if not can_access_page(user.roles, page):
        raise HTTPException(status_code=403, detail=f"Access denied for {page}")
