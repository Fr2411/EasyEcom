from __future__ import annotations

from dataclasses import dataclass

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
from easy_ecom.data.repos.factory import build_product_stock_repos
from easy_ecom.data.repos.postgres.auth_repo import PostgresAuthRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.postgres_db import build_postgres_engine, build_session_factory
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.auth_service import AuthService
from easy_ecom.domain.services.catalog_stock_service import CatalogStockService
from easy_ecom.domain.services.dashboard_service import DashboardService
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService
from easy_ecom.domain.services.sales_service import SalesService
from easy_ecom.domain.services.user_service import UserService


@dataclass
class RequestUser:
    user_id: str
    client_id: str
    roles: list[str]


class ServiceContainer:
    def __init__(self) -> None:
        self.store = CsvStore(settings.data_dir)
        self.users = UserService(
            UsersRepo(self.store), RolesRepo(self.store), UserRolesRepo(self.store)
        )
        self.sequence = SequenceService(SequencesRepo(self.store))
        if settings.storage_backend == "postgres":
            engine = build_postgres_engine(settings)
            self.auth = AuthService(PostgresAuthRepo(build_session_factory(engine)))
        else:
            self.auth = AuthService(CsvAuthRepo(UsersRepo(self.store), UserRolesRepo(self.store)))

        product_stock_repos = build_product_stock_repos(settings, self.store)
        self.products = ProductService(
            product_stock_repos.products, product_stock_repos.product_variants
        )
        self.inventory = InventoryService(
            product_stock_repos.inventory_txn,
            self.sequence,
            products_repo=product_stock_repos.products,
            variants_repo=product_stock_repos.product_variants,
        )
        self.catalog_stock = CatalogStockService(self.products, self.inventory)
        self.dashboard = DashboardService(
            InventoryTxnRepo(self.store),
            LedgerRepo(self.store),
            SalesOrdersRepo(self.store),
            InvoicesRepo(self.store),
            SalesOrderItemsRepo(self.store),
            ProductsRepo(self.store),
            ProductVariantsRepo(self.store),
            ClientsRepo(self.store),
            PaymentsRepo(self.store),
        )
        self.sales = SalesService(
            SalesOrdersRepo(self.store),
            SalesOrderItemsRepo(self.store),
            InvoicesRepo(self.store),
            ShipmentsRepo(self.store),
            PaymentsRepo(self.store),
            self.inventory,
            self.sequence,
            FinanceService(LedgerRepo(self.store), InventoryTxnRepo(self.store)),
            ProductsRepo(self.store),
            CustomersRepo(self.store),
            AuditRepo(self.store),
            ProductVariantsRepo(self.store),
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


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> RequestUser:
    if not session_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    payload = _signer().loads(session_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return RequestUser(
        user_id=str(payload.get("user_id", "")),
        client_id=str(payload.get("client_id", "")),
        roles=[str(r) for r in payload.get("roles", [])],
    )


def get_authenticated_user(
    user: RequestUser = Depends(get_current_user),
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> AuthenticatedUser:
    payload = _signer().loads(session_token or "") or {}
    return AuthenticatedUser(
        user_id=user.user_id,
        client_id=user.client_id,
        roles=user.roles,
        email=str(payload.get("email", "")),
        name=str(payload.get("name", "")),
    )


def require_page_access(user: RequestUser, page: str) -> None:
    if not can_access_page(user.roles, page):
        raise HTTPException(status_code=403, detail=f"Access denied for {page}")
