from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.api.schemas.reports import (
    ReportDeferredMetric,
    ReportTrendPoint,
    SalesReport,
    InventoryReport,
    ProductsReport,
    FinanceReport,
    ReturnsReport,
    PurchasesReport,
    ReportsOverview,
)
from easy_ecom.data.store.postgres_models import (
    CategoryModel,
    ClientModel,
    ClientSettingsModel,
    CustomerModel,
    ExpenseModel,
    InventoryLedgerModel,
    LocationModel,
    PaymentModel,
    ProductModel,
    ProductVariantModel,
    PurchaseModel,
    SalesOrderModel,
    SalesOrderItemModel,
    SalesReturnModel,
    SupplierModel,
    ShipmentModel,
    UserModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser


@dataclass(frozen=True)
class ReportContext:
    user: AuthenticatedUser

    @property
    def is_super_admin(self) -> bool:
        return "SUPER_ADMIN" in self.user.roles


class ReportsService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _apply_tenant_filter(self, stmt, model, context: ReportContext):
        if hasattr(model, "client_id") and not context.is_super_admin:
            return stmt.where(model.client_id == context.user.client_id)
        return stmt

    def _get_date_range(self, from_date: Optional[str], to_date: Optional[str]) -> tuple[datetime, datetime]:
        if from_date and to_date:
            start = datetime.fromisoformat(from_date)
            end = datetime.fromisoformat(to_date)
        else:
            # Default to last 30 days
            end = datetime.now()
            start = end - timedelta(days=30)
        return start, end

    def _count(self, session: Session, model, context: ReportContext) -> int:
        stmt = select(func.count()).select_from(model)
        stmt = self._apply_tenant_filter(stmt, model, context)
        return int(session.execute(stmt).scalar_one() or 0)

    def _sum(self, session: Session, model, column, context: ReportContext) -> float:
        stmt = select(func.sum(column)).select_from(model)
        stmt = self._apply_tenant_filter(stmt, model, context)
        result = session.execute(stmt).scalar_one_or_none()
        return float(result or 0)

    def get_sales_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> SalesReport:
        context = ReportContext(user)
        start_date, end_date = self._get_date_range(from_date, to_date)
        
        with self._session_factory() as session:
            # Sales count and revenue
            sales_stmt = select(
                func.count(SalesOrderModel.sales_order_id),
                func.sum(SalesOrderModel.total_amount)
            ).where(
                and_(
                    SalesOrderModel.ordered_at >= start_date,
                    SalesOrderModel.ordered_at <= end_date,
                    SalesOrderModel.status.in_(["confirmed", "shipped", "delivered"])
                )
            )
            sales_stmt = self._apply_tenant_filter(sales_stmt, SalesOrderModel, context)
            sales_count, revenue_total = session.execute(sales_stmt).one()
            sales_count = int(sales_count or 0)
            revenue_total = float(revenue_total or 0)

            # Sales trend (daily for last 30 days)
            trend_stmt = select(
                func.date(SalesOrderModel.ordered_at).label("period"),
                func.sum(SalesOrderModel.total_amount).label("value")
            ).where(
                and_(
                    SalesOrderModel.ordered_at >= start_date,
                    SalesOrderModel.ordered_at <= end_date,
                    SalesOrderModel.status.in_(["confirmed", "shipped", "delivered"])
                )
            ).group_by(func.date(SalesOrderModel.ordered_at))
            trend_stmt = self._apply_tenant_filter(trend_stmt, SalesOrderModel, context)
            trend_results = session.execute(trend_stmt).all()
            sales_trend = [ReportTrendPoint(period=str(row.period), value=float(row.value or 0)) for row in trend_results]

            # Top products
            top_products_stmt = select(
                ProductModel.id.label("product_id"),
                ProductModel.name.label("product_name"),
                func.sum(SalesOrderItemModel.quantity).label("qty_sold"),
                func.sum(SalesOrderItemModel.line_total_amount).label("revenue")
            ).select_from(
                SalesOrderModel.__table__.join(SalesOrderItemModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
                .join(ProductModel, SalesOrderItemModel.variant_id == ProductModel.id)
            ).where(
                and_(
                    SalesOrderModel.ordered_at >= start_date,
                    SalesOrderModel.ordered_at <= end_date,
                    SalesOrderModel.status.in_(["confirmed", "shipped", "delivered"])
                )
            ).group_by(ProductModel.id, ProductModel.name).order_by(func.sum(SalesOrderItemModel.line_total_amount).desc()).limit(10)
            top_products_stmt = self._apply_tenant_filter(top_products_stmt, SalesOrderModel, context)
            top_products_results = session.execute(top_products_stmt).all()
            top_products = [
                {
                    "product_id": str(row.product_id),
                    "product_name": row.product_name,
                    "qty_sold": int(row.qty_sold or 0),
                    "revenue": float(row.revenue or 0)
                }
                for row in top_products_results
            ]

            # Top customers
            top_customers_stmt = select(
                CustomerModel.id.label("customer_id"),
                CustomerModel.name.label("customer_name"),
                func.count(SalesOrderModel.sales_order_id).label("sales_count"),
                func.sum(SalesOrderModel.total_amount).label("revenue")
            ).select_from(
                SalesOrderModel.__table__.join(CustomerModel, SalesOrderModel.customer_id == CustomerModel.id)
            ).where(
                and_(
                    SalesOrderModel.ordered_at >= start_date,
                    SalesOrderModel.ordered_at <= end_date,
                    SalesOrderModel.status.in_(["confirmed", "shipped", "delivered"])
                )
            ).group_by(CustomerModel.id, CustomerModel.name).order_by(func.sum(SalesOrderModel.total_amount).desc()).limit(10)
            top_customers_stmt = self._apply_tenant_filter(top_customers_stmt, SalesOrderModel, context)
            top_customers_results = session.execute(top_customers_stmt).all()
            top_customers = [
                {
                    "customer_id": str(row.customer_id),
                    "customer_name": row.customer_name,
                    "sales_count": int(row.sales_count or 0),
                    "revenue": float(row.revenue or 0)
                }
                for row in top_customers_results
            ]

            return SalesReport(
                from_date=start_date.date().isoformat(),
                to_date=end_date.date().isoformat(),
                sales_count=sales_count,
                revenue_total=revenue_total,
                sales_trend=sales_trend,
                top_products=top_products,
                top_customers=top_customers,
                deferred_metrics=[]  # TODO: Implement deferred metrics calculation
            )

    def get_inventory_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> InventoryReport:
        context = ReportContext(user)
        start_date, end_date = self._get_date_range(from_date, to_date)
        
        with self._session_factory() as session:
            # Total SKUs with stock
            skus_stmt = select(func.count(ProductModel.id)).where(
                and_(
                    ProductModel.track_inventory == True,
                    ProductModel.quantity_in_stock > 0
                )
            )
            skus_stmt = self._apply_tenant_filter(skus_stmt, ProductModel, context)
            total_skus_with_stock = int(session.execute(skus_stmt).scalar_one() or 0)

            # Total stock units
            stock_stmt = select(func.sum(ProductModel.quantity_in_stock)).where(
                ProductModel.track_inventory == True
            )
            stock_stmt = self._apply_tenant_filter(stock_stmt, ProductModel, context)
            total_stock_units = int(session.execute(stock_stmt).scalar_one() or 0)

            # Low stock items (where quantity_in_stock <= low_stock_threshold)
            low_stock_stmt = select(
                ProductModel.id.label("product_id"),
                ProductModel.name.label("product_name"),
                ProductModel.quantity_in_stock.label("current_qty")
            ).where(
                and_(
                    ProductModel.track_inventory == True,
                    ProductModel.quantity_in_stock <= ProductModel.low_stock_threshold
                )
            )
            low_stock_stmt = self._apply_tenant_filter(low_stock_stmt, ProductModel, context)
            low_stock_results = session.execute(low_stock_stmt).all()
            low_stock_items = [
                {
                    "product_id": str(row.product_id),
                    "product_name": row.product_name,
                    "current_qty": int(row.current_qty or 0)
                }
                for row in low_stock_results
            ]

            # Stock movement trend (simplified: based on inventory ledger)
            movement_stmt = select(
                func.date(InventoryLedgerModel.created_at).label("period"),
                func.sum(
                    case(
                        (InventoryLedgerModel.change_type == "in", InventoryLedgerModel.quantity_change),
                        else_=0
                    )
                ).label("qty_in"),
                func.sum(
                    case(
                        (InventoryLedgerModel.change_type == "out", InventoryLedgerModel.quantity_change),
                        else_=0
                    )
                ).label("qty_out")
            ).where(
                and_(
                    InventoryLedgerModel.created_at >= start_date,
                    InventoryLedgerModel.created_at <= end_date
                )
            ).group_by(func.date(InventoryLedgerModel.created_at))
            movement_stmt = self._apply_tenant_filter(movement_stmt, InventoryLedgerModel, context)
            movement_results = session.execute(movement_stmt).all()
            stock_movement_trend = [
                {
                    "period": str(row.period),
                    "qty_in": int(row.qty_in or 0),
                    "qty_out": int(row.qty_out or 0)
                }
                for row in movement_results
            ]

            # Inventory value (simplified: sum of quantity * cost_price)
            value_stmt = select(
                func.sum(ProductModel.quantity_in_stock * ProductModel.cost_price)
            ).where(
                ProductModel.track_inventory == True
            )
            value_stmt = self._apply_tenant_filter(value_stmt, ProductModel, context)
            inventory_value = float(session.execute(value_stmt).scalar_one_or_none() or 0)

            return InventoryReport(
                from_date=start_date.date().isoformat(),
                to_date=end_date.date().isoformat(),
                total_skus_with_stock=total_skus_with_stock,
                total_stock_units=total_stock_units,
                low_stock_items=low_stock_items,
                stock_movement_trend=stock_movement_trend,
                inventory_value=inventory_value,
                deferred_metrics=[]
            )

    def get_products_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> ProductsReport:
        context = ReportContext(user)
        start_date, end_date = self._get_date_range(from_date, to_date)
        
        with self._session_factory() as session:
            # Highest selling products
            highest_selling_stmt = select(
                ProductModel.id.label("product_id"),
                ProductModel.name.label("product_name"),
                func.sum(SalesOrderModel.quantity).label("qty_sold"),
                func.sum(SalesOrderModel.total_amount).label("revenue")
            ).select_from(
                SalesOrderModel.__table__.join(ProductModel, SalesOrderModel.product_id == ProductModel.id)
            ).where(
                and_(
                    SalesOrderModel.ordered_at >= start_date,
                    SalesOrderModel.ordered_at <= end_date,
                    SalesOrderModel.status.in_(["confirmed", "shipped", "delivered"])
                )
            ).group_by(ProductModel.id, ProductModel.name).order_by(func.sum(SalesOrderModel.quantity).desc()).limit(10)
            highest_selling_stmt = self._apply_tenant_filter(highest_selling_stmt, SalesOrderModel, context)
            highest_selling_results = session.execute(highest_selling_stmt).all()
            highest_selling = [
                {
                    "product_id": str(row.product_id),
                    "product_name": row.product_name,
                    "qty_sold": int(row.qty_sold or 0),
                    "revenue": float(row.revenue or 0)
                }
                for row in highest_selling_results
            ]

            # Low or zero movement products (no sales in period)
            low_movement_stmt = select(
                ProductModel.id.label("product_id"),
                ProductModel.name.label("product_name"),
                func.coalesce(func.sum(SalesOrderModel.quantity), 0).label("qty_sold"),
                func.coalesce(func.sum(SalesOrderModel.total_amount), 0).label("revenue")
            ).select_from(
                ProductModel.__table__.outerjoin(
                    SalesOrderModel,
                    and_(
                        SalesOrderModel.product_id == ProductModel.id,
                        SalesOrderModel.ordered_at >= start_date,
                        SalesOrderModel.ordered_at <= end_date,
                        SalesOrderModel.status.in_(["confirmed", "shipped", "delivered"])
                    )
                )
            ).where(
                ProductModel.track_inventory == True
            ).group_by(ProductModel.id, ProductModel.name).having(
                func.coalesce(func.sum(SalesOrderModel.quantity), 0) == 0
            ).order_by(ProductModel.name).limit(10)
            low_movement_stmt = self._apply_tenant_filter(low_movement_stmt, ProductModel, context)
            low_movement_results = session.execute(low_movement_stmt).all()
            low_or_zero_movement = [
                {
                    "product_id": str(row.product_id),
                    "product_name": row.product_name,
                    "qty_sold": int(row.qty_sold or 0),
                    "revenue": float(row.revenue or 0)
                }
                for row in low_movement_results
            ]

            return ProductsReport(
                from_date=start_date.date().isoformat(),
                to_date=end_date.date().isoformat(),
                highest_selling=highest_selling,
                low_or_zero_movement=low_or_zero_movement,
                deferred_metrics=[]
            )

    def get_finance_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> FinanceReport:
        context = ReportContext(user)
        start_date, end_date = self._get_date_range(from_date, to_date)
        
        with self._session_factory() as session:
            # Expense total
            expense_stmt = select(func.sum(ExpenseModel.amount)).where(
                and_(
                    ExpenseModel.incurred_at >= start_date,
                    ExpenseModel.incurred_at <= end_date
                )
            )
            expense_stmt = self._apply_tenant_filter(expense_stmt, ExpenseModel, context)
            expense_total = float(session.execute(expense_stmt).scalar_one_or_none() or 0)

            # Expense trend (daily)
            expense_trend_stmt = select(
                func.date(ExpenseModel.incurred_at).label("period"),
                func.sum(ExpenseModel.amount).label("amount")
            ).where(
                and_(
                    ExpenseModel.incurred_at >= start_date,
                    ExpenseModel.incurred_at <= end_date
                )
            ).group_by(func.date(ExpenseModel.incurred_at))
            expense_trend_stmt = self._apply_tenant_filter(expense_trend_stmt, ExpenseModel, context)
            expense_trend_results = session.execute(expense_trend_stmt).all()
            expense_trend = [
                {
                    "period": str(row.period),
                    "amount": float(row.amount or 0)
                }
                for row in expense_trend_results
            ]

            # Receivables total (unpaid sales orders)
            receivables_stmt = select(func.sum(SalesOrderModel.total_amount)).where(
                and_(
                    SalesOrderModel.ordered_at >= start_date,
                    SalesOrderModel.ordered_at <= end_date,
                    SalesOrderModel.payment_status == "pending"
                )
            )
            receivables_stmt = self._apply_tenant_filter(receivables_stmt, SalesOrderModel, context)
            receivables_total = float(session.execute(receivables_stmt).scalar_one_or_none() or 0)

            # Payables total (unpaid purchase orders)
            payables_stmt = select(func.sum(PurchaseModel.total_amount)).where(
                and_(
                    PurchaseModel.ordered_at >= start_date,
                    PurchaseModel.ordered_at <= end_date,
                    PurchaseModel.payment_status == "pending"
                )
            )
            payables_stmt = self._apply_tenant_filter(payables_stmt, PurchaseModel, context)
            payables_total = float(session.execute(payables_stmt).scalar_one_or_none() or 0)

            # Net operating snapshot (revenue - expenses)
            revenue_stmt = select(func.sum(SalesOrderModel.total_amount)).where(
                and_(
                    SalesOrderModel.ordered_at >= start_date,
                    SalesOrderModel.ordered_at <= end_date,
                    SalesOrderModel.status.in_(["confirmed", "shipped", "delivered"]),
                    SalesOrderModel.payment_status == "paid"
                )
            )
            revenue_stmt = self._apply_tenant_filter(revenue_stmt, SalesOrderModel, context)
            revenue_total = float(session.execute(revenue_stmt).scalar_one_or_none() or 0)
            net_operating_snapshot = revenue_total - expense_total

            return FinanceReport(
                from_date=start_date.date().isoformat(),
                to_date=end_date.date().isoformat(),
                expense_total=expense_total,
                expense_trend=expense_trend,
                receivables_total=receivables_total,
                payables_total=payables_total,
                net_operating_snapshot=net_operating_snapshot,
                deferred_metrics=[]
            )

    def get_returns_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> ReturnsReport:
        context = ReportContext(user)
        start_date, end_date = self._get_date_range(from_date, to_date)
        
        with self._session_factory() as session:
            # Returns count
            returns_stmt = select(func.count(SalesReturnModel.sales_return_id)).where(
                and_(
                    SalesReturnModel.requested_at >= start_date,
                    SalesReturnModel.requested_at <= end_date
                )
            )
            returns_stmt = self._apply_tenant_filter(returns_stmt, SalesReturnModel, context)
            returns_count = int(session.execute(returns_stmt).scalar_one() or 0)

            # Return quantity total
            return_qty_stmt = select(0).where(
                and_(
                    SalesReturnModel.requested_at >= start_date,
                    SalesReturnModel.requested_at <= end_date
                )
            )
            return_qty_stmt = self._apply_tenant_filter(return_qty_stmt, SalesReturnModel, context)
            return_qty_total = int(session.execute(return_qty_stmt).scalar_one() or 0)

            # Return amount total
            return_amount_stmt = select(func.sum(SalesReturnModel.refund_amount)).where(
                and_(
                    SalesReturnModel.requested_at >= start_date,
                    SalesReturnModel.requested_at <= end_date
                )
            )
            return_amount_stmt = self._apply_tenant_filter(return_amount_stmt, SalesReturnModel, context)
            return_amount_total = float(session.execute(return_amount_stmt).scalar_one() or 0)

            return ReturnsReport(
                from_date=start_date.date().isoformat(),
                to_date=end_date.date().isoformat(),
                returns_count=returns_count,
                return_qty_total=return_qty_total,
                return_amount_total=return_amount_total,
                deferred_metrics=[]
            )

    def get_purchases_report(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> PurchasesReport:
        context = ReportContext(user)
        start_date, end_date = self._get_date_range(from_date, to_date)
        
        with self._session_factory() as session:
            # Purchases count
            purchases_stmt = select(func.count(PurchaseModel.id)).where(
                and_(
                    PurchaseModel.ordered_at >= start_date,
                    PurchaseModel.ordered_at <= end_date
                )
            )
            purchases_stmt = self._apply_tenant_filter(purchases_stmt, PurchaseModel, context)
            purchases_count = int(session.execute(purchases_stmt).scalar_one() or 0)

            # Purchases subtotal
            subtotal_stmt = select(func.sum(PurchaseModel.total_amount)).where(
                and_(
                    PurchaseModel.ordered_at >= start_date,
                    PurchaseModel.ordered_at <= end_date
                )
            )
            subtotal_stmt = self._apply_tenant_filter(subtotal_stmt, PurchaseModel, context)
            purchases_subtotal = float(session.execute(subtotal_stmt).scalar_one() or 0)

            # Purchases trend (daily)
            purchases_trend_stmt = select(
                func.date(PurchaseModel.ordered_at).label("period"),
                func.sum(PurchaseModel.total_amount).label("subtotal"),
                func.sum(PurchaseModel.quantity).label("quantity")
            ).where(
                and_(
                    PurchaseModel.ordered_at >= start_date,
                    PurchaseModel.ordered_at <= end_date
                )
            ).group_by(func.date(PurchaseModel.ordered_at))
            purchases_trend_stmt = self._apply_tenant_filter(purchases_trend_stmt, PurchaseModel, context)
            purchases_trend_results = session.execute(purchases_trend_stmt).all()
            purchases_trend = [
                {
                    "period": str(row.period),
                    "subtotal": float(row.subtotal or 0),
                    "quantity": int(row.quantity or 0)
                }
                for row in purchases_trend_results
            ]

            return PurchasesReport(
                from_date=start_date.date().isoformat(),
                to_date=end_date.date().isoformat(),
                purchases_count=purchases_count,
                purchases_subtotal=purchases_subtotal,
                purchases_trend=purchases_trend,
                deferred_metrics=[]
            )

    def get_reports_overview(self, user: AuthenticatedUser, from_date: Optional[str] = None, to_date: Optional[str] = None) -> ReportsOverview:
        context = ReportContext(user)
        start_date, end_date = self._get_date_range(from_date, to_date)
        
        with self._session_factory() as session:
            # Sales revenue total
            sales_revenue_stmt = select(func.sum(SalesOrderModel.total_amount)).where(
                and_(
                    SalesOrderModel.ordered_at >= start_date,
                    SalesOrderModel.ordered_at <= end_date,
                    SalesOrderModel.status.in_(["confirmed", "shipped", "delivered"]),
                    SalesOrderModel.payment_status == "paid"
                )
            )
            sales_revenue_stmt = self._apply_tenant_filter(sales_revenue_stmt, SalesOrderModel, context)
            sales_revenue_total = float(session.execute(sales_revenue_stmt).scalar_one_or_none() or 0)

            # Sales count
            sales_count_stmt = select(func.count(SalesOrderModel.sales_order_id)).where(
                and_(
                    SalesOrderModel.ordered_at >= start_date,
                    SalesOrderModel.ordered_at <= end_date,
                    SalesOrderModel.status.in_(["confirmed", "shipped", "delivered"])
                )
            )
            sales_count_stmt = self._apply_tenant_filter(sales_count_stmt, SalesOrderModel, context)
            sales_count = int(session.execute(sales_count_stmt).scalar_one() or 0)

            # Expense total
            expense_stmt = select(func.sum(ExpenseModel.amount)).where(
                and_(
                    ExpenseModel.incurred_at >= start_date,
                    ExpenseModel.incurred_at <= end_date
                )
            )
            expense_stmt = self._apply_tenant_filter(expense_stmt, ExpenseModel, context)
            expense_total = float(session.execute(expense_stmt).scalar_one_or_none() or 0)

            # Returns total
            returns_stmt = select(func.sum(SalesReturnModel.refund_amount)).where(
                and_(
                    SalesReturnModel.requested_at >= start_date,
                    SalesReturnModel.requested_at <= end_date
                )
            )
            returns_stmt = self._apply_tenant_filter(returns_stmt, SalesReturnModel, context)
            returns_total = int(session.execute(returns_stmt).scalar_one() or 0)

            # Purchases total
            purchases_stmt = select(func.sum(PurchaseModel.total_amount)).where(
                and_(
                    PurchaseModel.ordered_at >= start_date,
                    PurchaseModel.ordered_at <= end_date
                )
            )
            purchases_stmt = self._apply_tenant_filter(purchases_stmt, PurchaseModel, context)
            purchases_total = float(session.execute(purchases_stmt).scalar_one_or_none() or 0)

            return ReportsOverview(
                from_date=start_date.date().isoformat(),
                to_date=end_date.date().isoformat(),
                sales_revenue_total=sales_revenue_total,
                sales_count=sales_count,
                expense_total=expense_total,
                returns_total=returns_total,
                purchases_total=purchases_total
            )