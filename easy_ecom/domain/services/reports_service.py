from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.api.schemas.finance import FinanceOverviewResponse
from easy_ecom.api.schemas.reports import (
    FinanceReport,
    InventoryReport,
    ProductsReport,
    PurchasesReport,
    ReportDeferredMetric,
    ReportTrendPoint,
    ReportsOverview,
    ReturnsReport,
    SalesReport,
)
from easy_ecom.data.store.postgres_models import (
    CustomerModel,
    ExpenseModel,
    InventoryLedgerModel,
    PaymentModel,
    ProductModel,
    ProductVariantModel,
    PurchaseItemModel,
    PurchaseModel,
    SalesOrderItemModel,
    SalesOrderModel,
    SalesReturnItemModel,
    SalesReturnModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser

ZERO = Decimal("0")
COMPLETED_ORDER_STATUSES = ("completed",)
OPEN_ORDER_STATUSES = ("confirmed", "completed")
RECEIVED_PURCHASE_STATUSES = ("received",)
COMPLETED_PAYMENT_STATUSES = ("completed", "paid", "succeeded")
PAID_EXPENSE_STATUSES = ("paid", "completed")


def _as_decimal(value: object | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _as_float(value: object | None) -> float:
    return float(_as_decimal(value))


def _as_int(value: object | None) -> int:
    return int(_as_decimal(value))


@dataclass(frozen=True)
class ReportContext:
    user: AuthenticatedUser

    @property
    def is_super_admin(self) -> bool:
        return "SUPER_ADMIN" in self.user.roles


@dataclass(frozen=True)
class DateRange:
    start: datetime
    end_exclusive: datetime
    from_date: str
    to_date: str


@dataclass(frozen=True)
class SalesSummary:
    order_count: int
    revenue_total: Decimal


@dataclass(frozen=True)
class PurchaseSummary:
    purchase_count: int
    subtotal: Decimal


@dataclass(frozen=True)
class ReturnSummary:
    returns_count: int
    quantity_total: Decimal
    amount_total: Decimal


class ReportsService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _date_range(self, from_date: Optional[str], to_date: Optional[str]) -> DateRange:
        if from_date and to_date:
            start_day = date.fromisoformat(from_date)
            end_day = date.fromisoformat(to_date)
        else:
            end_day = datetime.utcnow().date()
            start_day = end_day - timedelta(days=29)
        return DateRange(
            start=datetime.combine(start_day, time.min),
            end_exclusive=datetime.combine(end_day + timedelta(days=1), time.min),
            from_date=start_day.isoformat(),
            to_date=end_day.isoformat(),
        )

    def _tenant_filters(self, context: ReportContext, *models: object):
        if context.is_super_admin:
            return []
        filters = []
        for model in models:
            client_id = getattr(model, "client_id", None)
            if client_id is not None:
                filters.append(client_id == context.user.client_id)
        return filters

    def _sales_event_expr(self):
        return func.coalesce(
            SalesOrderModel.confirmed_at,
            SalesOrderModel.ordered_at,
            SalesOrderModel.created_at,
        )

    def _purchase_event_expr(self):
        return func.coalesce(
            PurchaseModel.received_at,
            PurchaseModel.ordered_at,
            PurchaseModel.created_at,
        )

    def _return_event_expr(self):
        return func.coalesce(
            SalesReturnModel.received_at,
            SalesReturnModel.requested_at,
            SalesReturnModel.created_at,
        )

    def _payment_event_expr(self):
        return func.coalesce(
            PaymentModel.paid_at,
            PaymentModel.created_at,
        )

    def _expense_event_expr(self):
        return func.coalesce(
            ExpenseModel.incurred_at,
            ExpenseModel.created_at,
        )

    def _sales_summary(self, session: Session, context: ReportContext, date_range: DateRange) -> SalesSummary:
        sales_event = self._sales_event_expr()
        row = session.execute(
            select(
                func.count(func.distinct(SalesOrderItemModel.sales_order_id)),
                func.coalesce(func.sum(SalesOrderItemModel.line_total_amount), 0),
            )
            .select_from(SalesOrderItemModel)
            .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
            .where(
                *self._tenant_filters(context, SalesOrderItemModel, SalesOrderModel),
                SalesOrderModel.status.in_(COMPLETED_ORDER_STATUSES),
                sales_event >= date_range.start,
                sales_event < date_range.end_exclusive,
            )
        ).one()
        return SalesSummary(
            order_count=int(row[0] or 0),
            revenue_total=_as_decimal(row[1]),
        )

    def _purchase_summary(self, session: Session, context: ReportContext, date_range: DateRange) -> PurchaseSummary:
        purchase_event = self._purchase_event_expr()
        row = session.execute(
            select(
                func.count(func.distinct(PurchaseItemModel.purchase_id)),
                func.coalesce(func.sum(PurchaseItemModel.line_total_amount), 0),
            )
            .select_from(PurchaseItemModel)
            .join(PurchaseModel, PurchaseModel.purchase_id == PurchaseItemModel.purchase_id)
            .where(
                *self._tenant_filters(context, PurchaseItemModel, PurchaseModel),
                PurchaseModel.status.in_(RECEIVED_PURCHASE_STATUSES),
                purchase_event >= date_range.start,
                purchase_event < date_range.end_exclusive,
            )
        ).one()
        return PurchaseSummary(
            purchase_count=int(row[0] or 0),
            subtotal=_as_decimal(row[1]),
        )

    def _return_summary(self, session: Session, context: ReportContext, date_range: DateRange) -> ReturnSummary:
        return_event = self._return_event_expr()
        row = session.execute(
            select(
                func.count(func.distinct(SalesReturnItemModel.sales_return_id)),
                func.coalesce(func.sum(SalesReturnItemModel.quantity), 0),
                func.coalesce(
                    func.sum(SalesReturnItemModel.quantity * SalesReturnItemModel.unit_refund_amount),
                    0,
                ),
            )
            .select_from(SalesReturnItemModel)
            .join(SalesReturnModel, SalesReturnModel.sales_return_id == SalesReturnItemModel.sales_return_id)
            .where(
                *self._tenant_filters(context, SalesReturnItemModel, SalesReturnModel),
                return_event >= date_range.start,
                return_event < date_range.end_exclusive,
            )
        ).one()
        return ReturnSummary(
            returns_count=int(row[0] or 0),
            quantity_total=_as_decimal(row[1]),
            amount_total=_as_decimal(row[2]),
        )

    def _expense_total(self, session: Session, context: ReportContext, date_range: DateRange) -> Decimal:
        expense_event = self._expense_event_expr()
        value = session.execute(
            select(func.coalesce(func.sum(ExpenseModel.amount), 0)).where(
                *self._tenant_filters(context, ExpenseModel),
                expense_event >= date_range.start,
                expense_event < date_range.end_exclusive,
            )
        ).scalar_one()
        return _as_decimal(value)

    def _receivables_total(self, session: Session, context: ReportContext, date_range: DateRange) -> Decimal:
        payment_event = self._payment_event_expr()
        payments_subquery = (
            select(
                PaymentModel.sales_order_id.label("sales_order_id"),
                func.coalesce(func.sum(PaymentModel.amount), 0).label("paid_amount"),
            )
            .where(
                *self._tenant_filters(context, PaymentModel),
                PaymentModel.sales_order_id.is_not(None),
                PaymentModel.status.in_(COMPLETED_PAYMENT_STATUSES),
                payment_event < date_range.end_exclusive,
            )
            .group_by(PaymentModel.sales_order_id)
            .subquery()
        )

        sales_event = self._sales_event_expr()
        rows = session.execute(
            select(
                SalesOrderModel.total_amount,
                payments_subquery.c.paid_amount,
            )
            .select_from(SalesOrderModel)
            .outerjoin(payments_subquery, payments_subquery.c.sales_order_id == SalesOrderModel.sales_order_id)
            .where(
                *self._tenant_filters(context, SalesOrderModel),
                SalesOrderModel.status.in_(OPEN_ORDER_STATUSES),
                sales_event >= date_range.start,
                sales_event < date_range.end_exclusive,
            )
        ).all()

        outstanding = ZERO
        for total_amount, paid_amount in rows:
            balance = _as_decimal(total_amount) - _as_decimal(paid_amount)
            if balance > ZERO:
                outstanding += balance
        return outstanding

    def get_finance_overview(self, user: AuthenticatedUser) -> FinanceOverviewResponse:
        context = ReportContext(user)
        date_range = self._date_range(None, None)
        payment_event = self._payment_event_expr()
        expense_event = self._expense_event_expr()

        with self._session_factory() as session:
            sales_summary = self._sales_summary(session, context, date_range)
            expense_total = self._expense_total(session, context, date_range)
            receivables = self._receivables_total(session, context, date_range)

            cash_in = _as_decimal(
                session.execute(
                    select(func.coalesce(func.sum(PaymentModel.amount), 0)).where(
                        *self._tenant_filters(context, PaymentModel),
                        PaymentModel.status.in_(COMPLETED_PAYMENT_STATUSES),
                        PaymentModel.sales_order_id.is_not(None),
                        payment_event >= date_range.start,
                        payment_event < date_range.end_exclusive,
                    )
                ).scalar_one()
            )

            refund_cash_out = _as_decimal(
                session.execute(
                    select(func.coalesce(func.sum(PaymentModel.amount), 0)).where(
                        *self._tenant_filters(context, PaymentModel),
                        PaymentModel.status.in_(COMPLETED_PAYMENT_STATUSES),
                        PaymentModel.sales_return_id.is_not(None),
                        payment_event >= date_range.start,
                        payment_event < date_range.end_exclusive,
                    )
                ).scalar_one()
            )

            paid_expenses = _as_decimal(
                session.execute(
                    select(func.coalesce(func.sum(ExpenseModel.amount), 0)).where(
                        *self._tenant_filters(context, ExpenseModel),
                        ExpenseModel.payment_status.in_(PAID_EXPENSE_STATUSES),
                        expense_event >= date_range.start,
                        expense_event < date_range.end_exclusive,
                    )
                ).scalar_one()
            )

            cash_out = refund_cash_out + paid_expenses
            return FinanceOverviewResponse(
                sales_revenue=_as_float(sales_summary.revenue_total),
                expense_total=_as_float(expense_total),
                receivables=_as_float(receivables),
                payables=None,
                cash_in=_as_float(cash_in),
                cash_out=_as_float(cash_out),
                net_operating=_as_float(cash_in - cash_out),
            )

    def get_sales_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> SalesReport:
        context = ReportContext(user)
        date_range = self._date_range(from_date, to_date)
        sales_event = self._sales_event_expr()

        with self._session_factory() as session:
            summary = self._sales_summary(session, context, date_range)

            trend_rows = session.execute(
                select(
                    func.date(sales_event).label("period"),
                    func.coalesce(func.sum(SalesOrderItemModel.line_total_amount), 0).label("value"),
                )
                .select_from(SalesOrderItemModel)
                .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
                .where(
                    *self._tenant_filters(context, SalesOrderItemModel, SalesOrderModel),
                    SalesOrderModel.status.in_(COMPLETED_ORDER_STATUSES),
                    sales_event >= date_range.start,
                    sales_event < date_range.end_exclusive,
                )
                .group_by(func.date(sales_event))
                .order_by(func.date(sales_event))
            ).all()

            top_product_rows = session.execute(
                select(
                    ProductModel.product_id,
                    ProductModel.name,
                    func.coalesce(func.sum(SalesOrderItemModel.quantity_fulfilled), func.sum(SalesOrderItemModel.quantity), 0),
                    func.coalesce(func.sum(SalesOrderItemModel.line_total_amount), 0),
                )
                .select_from(SalesOrderItemModel)
                .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
                .join(ProductVariantModel, ProductVariantModel.variant_id == SalesOrderItemModel.variant_id)
                .join(ProductModel, ProductModel.product_id == ProductVariantModel.product_id)
                .where(
                    *self._tenant_filters(context, SalesOrderItemModel, SalesOrderModel, ProductVariantModel, ProductModel),
                    SalesOrderModel.status.in_(COMPLETED_ORDER_STATUSES),
                    sales_event >= date_range.start,
                    sales_event < date_range.end_exclusive,
                )
                .group_by(ProductModel.product_id, ProductModel.name)
                .order_by(func.sum(SalesOrderItemModel.line_total_amount).desc(), ProductModel.name.asc())
                .limit(10)
            ).all()

            top_customer_rows = session.execute(
                select(
                    CustomerModel.customer_id,
                    CustomerModel.name,
                    func.count(func.distinct(SalesOrderModel.sales_order_id)),
                    func.coalesce(func.sum(SalesOrderItemModel.line_total_amount), 0),
                )
                .select_from(SalesOrderItemModel)
                .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
                .join(CustomerModel, CustomerModel.customer_id == SalesOrderModel.customer_id)
                .where(
                    *self._tenant_filters(context, SalesOrderItemModel, SalesOrderModel, CustomerModel),
                    SalesOrderModel.status.in_(COMPLETED_ORDER_STATUSES),
                    sales_event >= date_range.start,
                    sales_event < date_range.end_exclusive,
                )
                .group_by(CustomerModel.customer_id, CustomerModel.name)
                .order_by(func.sum(SalesOrderItemModel.line_total_amount).desc(), CustomerModel.name.asc())
                .limit(10)
            ).all()

            return SalesReport(
                from_date=date_range.from_date,
                to_date=date_range.to_date,
                sales_count=summary.order_count,
                revenue_total=_as_float(summary.revenue_total),
                sales_trend=[
                    ReportTrendPoint(period=str(row.period), value=_as_float(row.value))
                    for row in trend_rows
                ],
                top_products=[
                    {
                        "product_id": str(row[0]),
                        "product_name": row[1],
                        "qty_sold": _as_int(row[2]),
                        "revenue": _as_float(row[3]),
                    }
                    for row in top_product_rows
                ],
                top_customers=[
                    {
                        "customer_id": str(row[0]),
                        "customer_name": row[1],
                        "sales_count": int(row[2] or 0),
                        "revenue": _as_float(row[3]),
                    }
                    for row in top_customer_rows
                ],
                deferred_metrics=[],
            )

    def get_inventory_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> InventoryReport:
        context = ReportContext(user)
        date_range = self._date_range(from_date, to_date)

        stock_subquery = (
            select(
                InventoryLedgerModel.variant_id.label("variant_id"),
                func.coalesce(func.sum(InventoryLedgerModel.quantity_delta), 0).label("current_qty"),
            )
            .where(*self._tenant_filters(context, InventoryLedgerModel))
            .group_by(InventoryLedgerModel.variant_id)
            .subquery()
        )

        with self._session_factory() as session:
            stock_rows = session.execute(
                select(
                    ProductModel.product_id,
                    ProductModel.name,
                    ProductVariantModel.variant_id,
                    ProductVariantModel.sku,
                    ProductVariantModel.title,
                    ProductVariantModel.reorder_level,
                    ProductVariantModel.cost_amount,
                    func.coalesce(stock_subquery.c.current_qty, 0).label("current_qty"),
                )
                .select_from(ProductVariantModel)
                .join(ProductModel, ProductModel.product_id == ProductVariantModel.product_id)
                .outerjoin(stock_subquery, stock_subquery.c.variant_id == ProductVariantModel.variant_id)
                .where(
                    *self._tenant_filters(context, ProductVariantModel, ProductModel),
                    ProductVariantModel.status == "active",
                )
                .order_by(ProductModel.name.asc(), ProductVariantModel.sku.asc())
            ).all()

            total_skus_with_stock = 0
            total_stock_units = 0
            inventory_value = ZERO
            inventory_value_complete = True
            low_stock_items: list[dict[str, object]] = []

            for row in stock_rows:
                current_qty = _as_decimal(row.current_qty)
                reorder_level = _as_decimal(row.reorder_level)
                if current_qty > ZERO:
                    total_skus_with_stock += 1
                    total_stock_units += _as_int(current_qty)
                    if row.cost_amount is None:
                        inventory_value_complete = False
                    else:
                        inventory_value += current_qty * _as_decimal(row.cost_amount)
                if current_qty <= reorder_level:
                    low_stock_items.append(
                        {
                            "product_id": str(row.product_id),
                            "product_name": row.name,
                            "variant_id": str(row.variant_id),
                            "variant_label": row.title,
                            "sku": row.sku,
                            "current_qty": _as_int(current_qty),
                        }
                    )

            movement_rows = session.execute(
                select(
                    func.date(InventoryLedgerModel.created_at).label("period"),
                    func.coalesce(
                        func.sum(
                            case((InventoryLedgerModel.quantity_delta > 0, InventoryLedgerModel.quantity_delta), else_=0)
                        ),
                        0,
                    ).label("qty_in"),
                    func.coalesce(
                        func.sum(
                            case((InventoryLedgerModel.quantity_delta < 0, -InventoryLedgerModel.quantity_delta), else_=0)
                        ),
                        0,
                    ).label("qty_out"),
                )
                .where(
                    *self._tenant_filters(context, InventoryLedgerModel),
                    InventoryLedgerModel.created_at >= date_range.start,
                    InventoryLedgerModel.created_at < date_range.end_exclusive,
                )
                .group_by(func.date(InventoryLedgerModel.created_at))
                .order_by(func.date(InventoryLedgerModel.created_at))
            ).all()

            deferred_metrics: list[ReportDeferredMetric] = []
            if not inventory_value_complete:
                deferred_metrics.append(
                    ReportDeferredMetric(
                        metric="inventory_value",
                        reason="Disabled until all stocked variants have an explicit unit cost.",
                    )
                )

            return InventoryReport(
                from_date=date_range.from_date,
                to_date=date_range.to_date,
                total_skus_with_stock=total_skus_with_stock,
                total_stock_units=total_stock_units,
                low_stock_items=low_stock_items,
                stock_movement_trend=[
                    {
                        "period": str(row.period),
                        "qty_in": _as_int(row.qty_in),
                        "qty_out": _as_int(row.qty_out),
                    }
                    for row in movement_rows
                ],
                inventory_value=_as_float(inventory_value) if inventory_value_complete else None,
                deferred_metrics=deferred_metrics,
            )

    def get_products_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> ProductsReport:
        context = ReportContext(user)
        date_range = self._date_range(from_date, to_date)
        sales_event = self._sales_event_expr()

        sold_subquery = (
            select(
                ProductModel.product_id.label("product_id"),
                func.coalesce(func.sum(SalesOrderItemModel.quantity_fulfilled), func.sum(SalesOrderItemModel.quantity), 0).label("qty_sold"),
                func.coalesce(func.sum(SalesOrderItemModel.line_total_amount), 0).label("revenue"),
            )
            .select_from(SalesOrderItemModel)
            .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
            .join(ProductVariantModel, ProductVariantModel.variant_id == SalesOrderItemModel.variant_id)
            .join(ProductModel, ProductModel.product_id == ProductVariantModel.product_id)
            .where(
                *self._tenant_filters(context, SalesOrderItemModel, SalesOrderModel, ProductVariantModel, ProductModel),
                SalesOrderModel.status.in_(COMPLETED_ORDER_STATUSES),
                sales_event >= date_range.start,
                sales_event < date_range.end_exclusive,
            )
            .group_by(ProductModel.product_id)
            .subquery()
        )

        with self._session_factory() as session:
            highest_rows = session.execute(
                select(
                    ProductModel.product_id,
                    ProductModel.name,
                    func.coalesce(sold_subquery.c.qty_sold, 0),
                    func.coalesce(sold_subquery.c.revenue, 0),
                )
                .select_from(ProductModel)
                .join(sold_subquery, sold_subquery.c.product_id == ProductModel.product_id)
                .where(*self._tenant_filters(context, ProductModel))
                .order_by(sold_subquery.c.qty_sold.desc(), sold_subquery.c.revenue.desc(), ProductModel.name.asc())
                .limit(10)
            ).all()

            low_rows = session.execute(
                select(
                    ProductModel.product_id,
                    ProductModel.name,
                    func.coalesce(sold_subquery.c.qty_sold, 0),
                    func.coalesce(sold_subquery.c.revenue, 0),
                )
                .select_from(ProductModel)
                .outerjoin(sold_subquery, sold_subquery.c.product_id == ProductModel.product_id)
                .where(*self._tenant_filters(context, ProductModel))
                .order_by(
                    func.coalesce(sold_subquery.c.qty_sold, 0).asc(),
                    func.coalesce(sold_subquery.c.revenue, 0).asc(),
                    ProductModel.name.asc(),
                )
                .limit(10)
            ).all()

            return ProductsReport(
                from_date=date_range.from_date,
                to_date=date_range.to_date,
                highest_selling=[
                    {
                        "product_id": str(row[0]),
                        "product_name": row[1],
                        "qty_sold": _as_int(row[2]),
                        "revenue": _as_float(row[3]),
                    }
                    for row in highest_rows
                ],
                low_or_zero_movement=[
                    {
                        "product_id": str(row[0]),
                        "product_name": row[1],
                        "qty_sold": _as_int(row[2]),
                        "revenue": _as_float(row[3]),
                    }
                    for row in low_rows
                ],
                deferred_metrics=[],
            )

    def get_finance_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> FinanceReport:
        context = ReportContext(user)
        date_range = self._date_range(from_date, to_date)
        expense_event = self._expense_event_expr()

        with self._session_factory() as session:
            sales_summary = self._sales_summary(session, context, date_range)
            purchase_summary = self._purchase_summary(session, context, date_range)
            return_summary = self._return_summary(session, context, date_range)
            expense_total = self._expense_total(session, context, date_range)
            receivables_total = self._receivables_total(session, context, date_range)

            expense_trend_rows = session.execute(
                select(
                    func.date(expense_event).label("period"),
                    func.coalesce(func.sum(ExpenseModel.amount), 0).label("amount"),
                )
                .where(
                    *self._tenant_filters(context, ExpenseModel),
                    expense_event >= date_range.start,
                    expense_event < date_range.end_exclusive,
                )
                .group_by(func.date(expense_event))
                .order_by(func.date(expense_event))
            ).all()

            return FinanceReport(
                from_date=date_range.from_date,
                to_date=date_range.to_date,
                expense_total=_as_float(expense_total),
                expense_trend=[
                    {"period": str(row.period), "amount": _as_float(row.amount)}
                    for row in expense_trend_rows
                ],
                receivables_total=_as_float(receivables_total),
                payables_total=None,
                net_operating_snapshot=_as_float(
                    sales_summary.revenue_total - expense_total - purchase_summary.subtotal - return_summary.amount_total
                ),
                deferred_metrics=[
                    ReportDeferredMetric(
                        metric="payables_total",
                        reason="Disabled until supplier payment settlement is tracked canonically.",
                    )
                ],
            )

    def get_returns_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> ReturnsReport:
        context = ReportContext(user)
        date_range = self._date_range(from_date, to_date)

        with self._session_factory() as session:
            summary = self._return_summary(session, context, date_range)
            return ReturnsReport(
                from_date=date_range.from_date,
                to_date=date_range.to_date,
                returns_count=summary.returns_count,
                return_qty_total=_as_int(summary.quantity_total),
                return_amount_total=_as_float(summary.amount_total),
                deferred_metrics=[],
            )

    def get_purchases_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> PurchasesReport:
        context = ReportContext(user)
        date_range = self._date_range(from_date, to_date)
        purchase_event = self._purchase_event_expr()

        with self._session_factory() as session:
            summary = self._purchase_summary(session, context, date_range)
            trend_rows = session.execute(
                select(
                    func.date(purchase_event).label("period"),
                    func.coalesce(func.sum(PurchaseItemModel.line_total_amount), 0).label("subtotal"),
                    func.coalesce(func.sum(PurchaseItemModel.received_quantity), func.sum(PurchaseItemModel.quantity), 0).label("quantity"),
                )
                .select_from(PurchaseItemModel)
                .join(PurchaseModel, PurchaseModel.purchase_id == PurchaseItemModel.purchase_id)
                .where(
                    *self._tenant_filters(context, PurchaseItemModel, PurchaseModel),
                    PurchaseModel.status.in_(RECEIVED_PURCHASE_STATUSES),
                    purchase_event >= date_range.start,
                    purchase_event < date_range.end_exclusive,
                )
                .group_by(func.date(purchase_event))
                .order_by(func.date(purchase_event))
            ).all()

            return PurchasesReport(
                from_date=date_range.from_date,
                to_date=date_range.to_date,
                purchases_count=summary.purchase_count,
                purchases_subtotal=_as_float(summary.subtotal),
                purchases_trend=[
                    {
                        "period": str(row.period),
                        "subtotal": _as_float(row.subtotal),
                        "quantity": _as_int(row.quantity),
                    }
                    for row in trend_rows
                ],
                deferred_metrics=[],
            )

    def get_reports_overview(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> ReportsOverview:
        context = ReportContext(user)
        date_range = self._date_range(from_date, to_date)

        with self._session_factory() as session:
            sales_summary = self._sales_summary(session, context, date_range)
            purchase_summary = self._purchase_summary(session, context, date_range)
            return_summary = self._return_summary(session, context, date_range)
            expense_total = self._expense_total(session, context, date_range)

            return ReportsOverview(
                from_date=date_range.from_date,
                to_date=date_range.to_date,
                sales_revenue_total=_as_float(sales_summary.revenue_total),
                sales_count=sales_summary.order_count,
                expense_total=_as_float(expense_total),
                returns_total=_as_int(return_summary.quantity_total),
                purchases_total=_as_float(purchase_summary.subtotal),
            )
