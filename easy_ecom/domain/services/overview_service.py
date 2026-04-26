from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.api.schemas.common import ModuleOverviewResponse, OverviewMetric
from easy_ecom.data.store.postgres_models import (
    CategoryModel,
    ClientModel,
    ClientSettingsModel,
    CustomerChannelModel,
    CustomerConversationModel,
    CustomerModel,
    ExpenseModel,
    InventoryLedgerModel,
    LocationModel,
    PaymentModel,
    ProductModel,
    ProductVariantModel,
    PurchaseModel,
    SalesOrderModel,
    SalesReturnModel,
    SupplierModel,
    ShipmentModel,
    UserModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser


@dataclass(frozen=True)
class OverviewContext:
    user: AuthenticatedUser

    @property
    def is_super_admin(self) -> bool:
        return "SUPER_ADMIN" in self.user.roles


class OverviewService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _count(self, session: Session, model, context: OverviewContext) -> int:
        stmt = select(func.count()).select_from(model)
        if hasattr(model, "client_id") and not context.is_super_admin:
            stmt = stmt.where(model.client_id == context.user.client_id)
        return int(session.execute(stmt).scalar_one() or 0)

    def _count_where(self, session: Session, model, context: OverviewContext, *conditions) -> int:
        stmt = select(func.count()).select_from(model).where(*conditions)
        if hasattr(model, "client_id") and not context.is_super_admin:
            stmt = stmt.where(model.client_id == context.user.client_id)
        return int(session.execute(stmt).scalar_one() or 0)

    def _overview(self, module: str, summary: str, metrics: list[OverviewMetric]) -> ModuleOverviewResponse:
        return ModuleOverviewResponse(
            module=module,
            status="foundation",
            summary=summary,
            metrics=metrics,
        )

    def dashboard(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "dashboard",
                "Pilot-ready overview surfaces live counts while the detailed workflows are rebuilt.",
                [
                    OverviewMetric(label="Products", value=str(self._count(session, ProductModel, context))),
                    OverviewMetric(label="Variants", value=str(self._count(session, ProductVariantModel, context))),
                    OverviewMetric(label="Customers", value=str(self._count(session, CustomerModel, context))),
                    OverviewMetric(label="Sales Orders", value=str(self._count(session, SalesOrderModel, context))),
                ],
            )

    def catalog(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "catalog",
                "Catalog now has canonical typed tables for categories, suppliers, products, and variants.",
                [
                    OverviewMetric(label="Categories", value=str(self._count(session, CategoryModel, context))),
                    OverviewMetric(label="Suppliers", value=str(self._count(session, SupplierModel, context))),
                    OverviewMetric(label="Products", value=str(self._count(session, ProductModel, context))),
                    OverviewMetric(label="Variants", value=str(self._count(session, ProductVariantModel, context))),
                ],
            )

    def inventory(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "inventory",
                "Inventory is rebuilt around an immutable ledger and location-aware stock ownership.",
                [
                    OverviewMetric(label="Locations", value=str(self._count(session, LocationModel, context))),
                    OverviewMetric(label="Ledger Entries", value=str(self._count(session, InventoryLedgerModel, context))),
                    OverviewMetric(label="Shipments", value=str(self._count(session, ShipmentModel, context))),
                ],
            )

    def purchases(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "purchases",
                "Procurement now has dedicated purchase and purchase-item foundations.",
                [
                    OverviewMetric(label="Purchase Orders", value=str(self._count(session, PurchaseModel, context))),
                    OverviewMetric(
                        label="Received",
                        value=str(self._count_where(session, PurchaseModel, context, PurchaseModel.status == "received")),
                    ),
                ],
            )

    def customers(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "customers",
                "Customer identity is back as a first-class tenant-safe module.",
                [
                    OverviewMetric(label="Customers", value=str(self._count(session, CustomerModel, context))),
                ],
            )

    def customer_communication(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "customer_communication",
                "Customer communication connects channel conversations to grounded AI sales and support assistance.",
                [
                    OverviewMetric(label="Channels", value=str(self._count(session, CustomerChannelModel, context))),
                    OverviewMetric(label="Conversations", value=str(self._count(session, CustomerConversationModel, context))),
                    OverviewMetric(
                        label="Escalated",
                        value=str(
                            self._count_where(
                                session,
                                CustomerConversationModel,
                                context,
                                CustomerConversationModel.status == "escalated",
                            )
                        ),
                    ),
                ],
            )

    def sales(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "sales",
                "Sales orders now have dedicated order, line-item, payment, and shipment tables.",
                [
                    OverviewMetric(label="Orders", value=str(self._count(session, SalesOrderModel, context))),
                    OverviewMetric(label="Payments", value=str(self._count(session, PaymentModel, context))),
                    OverviewMetric(label="Shipments", value=str(self._count(session, ShipmentModel, context))),
                ],
            )

    def returns(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "returns",
                "Returns and refunds now have dedicated auditable tables and lifecycle states.",
                [
                    OverviewMetric(label="Return Requests", value=str(self._count(session, SalesReturnModel, context))),
                ],
            )

    def finance(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "finance",
                "Operational finance foundations now track payments, expenses, and return-linked money movement.",
                [
                    OverviewMetric(label="Payments", value=str(self._count(session, PaymentModel, context))),
                    OverviewMetric(label="Expenses", value=str(self._count(session, ExpenseModel, context))),
                ],
            )

    def reports(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "reports",
                "Reports are being rebuilt on top of canonical transactional tables rather than legacy calculations.",
                [
                    OverviewMetric(label="Products", value=str(self._count(session, ProductModel, context))),
                    OverviewMetric(label="Orders", value=str(self._count(session, SalesOrderModel, context))),
                    OverviewMetric(label="Returns", value=str(self._count(session, SalesReturnModel, context))),
                ],
            )

    def admin(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "admin",
                "Admin foundations now include tenant onboarding, users, and client settings.",
                [
                    OverviewMetric(label="Clients", value=str(self._count(session, ClientModel, context))),
                    OverviewMetric(label="Users", value=str(self._count(session, UserModel, context))),
                    OverviewMetric(label="Locations", value=str(self._count(session, LocationModel, context))),
                ],
            )

    def settings(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        context = OverviewContext(user)
        with self._session_factory() as session:
            return self._overview(
                "settings",
                "Settings foundations include tenant defaults and session-safe profile context.",
                [
                    OverviewMetric(label="Client Settings", value=str(self._count(session, ClientSettingsModel, context))),
                    OverviewMetric(label="Your Client", value=user.client_id, hint="Scoped tenant identity"),
                ],
            )
