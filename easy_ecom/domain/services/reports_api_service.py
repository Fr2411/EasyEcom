from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.domain.services.stock_policy import stock_deltas

from easy_ecom.data.store.postgres_models import (
    CustomerModel,
    FinanceExpenseModel,
    InventoryTxnModel,
    ProductModel,
    PurchaseItemModel,
    PurchaseModel,
    SalesOrderItemModel,
    SalesOrderModel,
    SalesReturnItemModel,
    SalesReturnModel,
)


@dataclass(frozen=True)
class ReportFilters:
    from_date: date
    to_date: date
    product_id: str | None = None
    category: str | None = None
    customer_id: str | None = None


class ReportsApiService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    @staticmethod
    def _to_float(value: str | float | int | None) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _day(ts: str) -> date | None:
        if not ts:
            return None
        raw = ts.strip()
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(raw[:10], "%Y-%m-%d").date()
            except ValueError:
                return None

    @staticmethod
    def _in_range(ts: str, filters: ReportFilters) -> bool:
        day = ReportsApiService._day(ts)
        return day is not None and filters.from_date <= day <= filters.to_date

    @staticmethod
    def build_filters(
        *,
        from_date: date | None,
        to_date: date | None,
        product_id: str,
        category: str,
        customer_id: str,
    ) -> ReportFilters:
        end = to_date or datetime.now(UTC).date()
        start = from_date or (end - timedelta(days=29))
        if start > end:
            raise ValueError("from_date must be <= to_date")
        return ReportFilters(
            from_date=start,
            to_date=end,
            product_id=product_id.strip() or None,
            category=category.strip() or None,
            customer_id=customer_id.strip() or None,
        )

    def sales_report(self, *, client_id: str, filters: ReportFilters) -> dict[str, object]:
        with self.session_factory() as session:
            orders = session.execute(
                select(SalesOrderModel).where(SalesOrderModel.client_id == client_id)
            ).scalars().all()
            order_items = session.execute(
                select(SalesOrderItemModel).where(SalesOrderItemModel.client_id == client_id)
            ).scalars().all()
            customers = session.execute(
                select(CustomerModel).where(CustomerModel.client_id == client_id)
            ).scalars().all()

        customer_name = {c.customer_id: c.full_name for c in customers}
        matched_orders = [
            o
            for o in orders
            if o.status == "confirmed"
            and self._in_range(o.timestamp, filters)
            and (not filters.customer_id or o.customer_id == filters.customer_id)
        ]
        order_ids = {o.order_id for o in matched_orders}
        revenue_total = sum(self._to_float(o.grand_total) for o in matched_orders)

        trend_by_day: dict[str, float] = defaultdict(float)
        customer_agg: dict[str, dict[str, float | int | str]] = defaultdict(
            lambda: {"sales_count": 0, "revenue": 0.0}
        )
        for order in matched_orders:
            day = self._day(order.timestamp)
            if day:
                trend_by_day[day.isoformat()] += self._to_float(order.grand_total)
            agg = customer_agg[order.customer_id]
            agg["sales_count"] = int(agg["sales_count"]) + 1
            agg["revenue"] = float(agg["revenue"]) + self._to_float(order.grand_total)

        product_agg: dict[str, dict[str, float | str]] = defaultdict(
            lambda: {"product_name": "", "qty_sold": 0.0, "revenue": 0.0}
        )
        for item in order_items:
            if item.order_id not in order_ids:
                continue
            if filters.product_id and item.product_id != filters.product_id:
                continue
            entry = product_agg[item.product_id]
            entry["product_name"] = item.product_name_snapshot or item.product_id
            entry["qty_sold"] = float(entry["qty_sold"]) + self._to_float(item.qty)
            entry["revenue"] = float(entry["revenue"]) + self._to_float(item.total_selling_price)

        top_products = sorted(
            [
                {
                    "product_id": pid,
                    "product_name": str(data["product_name"]),
                    "qty_sold": float(data["qty_sold"]),
                    "revenue": float(data["revenue"]),
                }
                for pid, data in product_agg.items()
            ],
            key=lambda row: (row["qty_sold"], row["revenue"]),
            reverse=True,
        )[:10]

        top_customers = sorted(
            [
                {
                    "customer_id": cid,
                    "customer_name": customer_name.get(cid, cid),
                    "sales_count": int(values["sales_count"]),
                    "revenue": float(values["revenue"]),
                }
                for cid, values in customer_agg.items()
            ],
            key=lambda row: (row["revenue"], row["sales_count"]),
            reverse=True,
        )[:10]

        return {
            "from_date": filters.from_date.isoformat(),
            "to_date": filters.to_date.isoformat(),
            "sales_count": len(matched_orders),
            "revenue_total": revenue_total,
            "sales_trend": [
                {"period": period, "value": value}
                for period, value in sorted(trend_by_day.items(), key=lambda x: x[0])
            ],
            "top_products": top_products,
            "top_customers": top_customers,
            "deferred_metrics": [],
        }

    def inventory_report(self, *, client_id: str, filters: ReportFilters) -> dict[str, object]:
        with self.session_factory() as session:
            products = session.execute(
                select(ProductModel).where(ProductModel.client_id == client_id)
            ).scalars().all()
            txns = session.execute(
                select(InventoryTxnModel).where(InventoryTxnModel.client_id == client_id)
            ).scalars().all()

        if filters.category:
            products = [p for p in products if (p.category or "") == filters.category]
        product_ids = {p.product_id for p in products}
        qty_by_product: dict[str, float] = defaultdict(float)
        for txn in txns:
            if txn.product_id not in product_ids:
                continue
            qty = self._to_float(txn.qty)
            qty_by_product[txn.product_id] += stock_deltas(str(txn.txn_type), qty).on_hand

        low = []
        total_units = 0.0
        for p in products:
            current = qty_by_product.get(p.product_id, 0.0)
            total_units += max(0.0, current)
            if current > 0 and current <= 5:
                low.append(
                    {
                        "product_id": p.product_id,
                        "product_name": p.product_name,
                        "current_qty": current,
                    }
                )

        movement: dict[str, dict[str, float]] = defaultdict(lambda: {"qty_in": 0.0, "qty_out": 0.0})
        for txn in txns:
            if txn.product_id not in product_ids or not self._in_range(txn.timestamp, filters):
                continue
            day = self._day(txn.timestamp)
            if not day:
                continue
            key = day.isoformat()
            signed = stock_deltas(str(txn.txn_type), self._to_float(txn.qty)).on_hand
            if signed > 0:
                movement[key]["qty_in"] += signed
            elif signed < 0:
                movement[key]["qty_out"] += abs(signed)

        return {
            "from_date": filters.from_date.isoformat(),
            "to_date": filters.to_date.isoformat(),
            "total_skus_with_stock": sum(1 for v in qty_by_product.values() if v > 0),
            "total_stock_units": total_units,
            "low_stock_items": sorted(low, key=lambda row: row["current_qty"])[:20],
            "stock_movement_trend": [
                {"period": period, "qty_in": row["qty_in"], "qty_out": row["qty_out"]}
                for period, row in sorted(movement.items(), key=lambda x: x[0])
            ],
            "inventory_value": None,
            "deferred_metrics": [
                {
                    "metric": "inventory_value",
                    "reason": "Lot-level outbound valuation is not consistently captured, so inventory value is deferred for truthful reporting.",
                }
            ],
        }

    def products_report(self, *, client_id: str, filters: ReportFilters) -> dict[str, object]:
        sales = self.sales_report(client_id=client_id, filters=filters)
        with self.session_factory() as session:
            products = session.execute(
                select(ProductModel).where(ProductModel.client_id == client_id)
            ).scalars().all()
        if filters.category:
            products = [p for p in products if (p.category or "") == filters.category]
        top = sales["top_products"]
        top_ids = {row["product_id"] for row in top}
        zero_movement = [
            {"product_id": p.product_id, "product_name": p.product_name, "qty_sold": 0.0, "revenue": 0.0}
            for p in products
            if p.product_id not in top_ids
        ][:20]
        return {
            "from_date": filters.from_date.isoformat(),
            "to_date": filters.to_date.isoformat(),
            "highest_selling": top,
            "low_or_zero_movement": zero_movement,
            "deferred_metrics": [],
        }

    def finance_report(self, *, client_id: str, filters: ReportFilters) -> dict[str, object]:
        with self.session_factory() as session:
            expenses = session.execute(
                select(FinanceExpenseModel).where(FinanceExpenseModel.client_id == client_id)
            ).scalars().all()
            orders = session.execute(
                select(SalesOrderModel).where(SalesOrderModel.client_id == client_id)
            ).scalars().all()
            purchases = session.execute(
                select(PurchaseModel).where(PurchaseModel.client_id == client_id)
            ).scalars().all()

        matched_expenses = [e for e in expenses if self._in_range(e.expense_date, filters)]
        expense_total = sum(self._to_float(e.amount) for e in matched_expenses)
        expense_trend: dict[str, float] = defaultdict(float)
        for e in matched_expenses:
            day = self._day(e.expense_date)
            if day:
                expense_trend[day.isoformat()] += self._to_float(e.amount)

        matched_orders = [o for o in orders if o.status == "confirmed" and self._in_range(o.timestamp, filters)]
        matched_purchases = [p for p in purchases if self._in_range(p.purchase_date, filters)]
        receivables_total = sum(self._to_float(o.outstanding_balance) for o in matched_orders)
        payables_total = sum(
            self._to_float(p.subtotal)
            for p in matched_purchases
            if (p.status or "").lower() not in {"paid", "closed"}
        )
        revenue_total = sum(self._to_float(o.grand_total) for o in matched_orders)

        return {
            "from_date": filters.from_date.isoformat(),
            "to_date": filters.to_date.isoformat(),
            "expense_total": expense_total,
            "expense_trend": [
                {"period": period, "amount": amount}
                for period, amount in sorted(expense_trend.items(), key=lambda x: x[0])
            ],
            "receivables_total": receivables_total,
            "payables_total": payables_total,
            "net_operating_snapshot": revenue_total - expense_total,
            "deferred_metrics": [
                {
                    "metric": "net_operating_snapshot",
                    "reason": "Snapshot excludes COGS due to incomplete sale-line cost capture in current data model.",
                }
            ],
        }

    def returns_report(self, *, client_id: str, filters: ReportFilters) -> dict[str, object]:
        with self.session_factory() as session:
            returns = session.execute(
                select(SalesReturnModel).where(SalesReturnModel.client_id == client_id)
            ).scalars().all()
            return_items = session.execute(
                select(SalesReturnItemModel).where(SalesReturnItemModel.client_id == client_id)
            ).scalars().all()
        matched_returns = [r for r in returns if self._in_range(r.created_at, filters)]
        return_ids = {r.return_id for r in matched_returns}
        qty_total = sum(self._to_float(item.return_qty) for item in return_items if item.return_id in return_ids)
        return {
            "from_date": filters.from_date.isoformat(),
            "to_date": filters.to_date.isoformat(),
            "returns_count": len(matched_returns),
            "return_qty_total": qty_total,
            "return_amount_total": sum(self._to_float(r.return_total) for r in matched_returns),
            "deferred_metrics": [],
        }

    def purchases_report(self, *, client_id: str, filters: ReportFilters) -> dict[str, object]:
        with self.session_factory() as session:
            purchases = session.execute(
                select(PurchaseModel).where(PurchaseModel.client_id == client_id)
            ).scalars().all()
            items = session.execute(
                select(PurchaseItemModel).where(PurchaseItemModel.client_id == client_id)
            ).scalars().all()
        matched_purchases = [p for p in purchases if self._in_range(p.purchase_date, filters)]
        purchase_ids = {p.purchase_id for p in matched_purchases}
        trend: dict[str, dict[str, float]] = defaultdict(lambda: {"subtotal": 0.0, "quantity": 0.0})
        for purchase in matched_purchases:
            day = self._day(purchase.purchase_date)
            if not day:
                continue
            trend[day.isoformat()]["subtotal"] += self._to_float(purchase.subtotal)
        for item in items:
            if item.purchase_id not in purchase_ids:
                continue
            purchase = next((p for p in matched_purchases if p.purchase_id == item.purchase_id), None)
            if purchase is None:
                continue
            day = self._day(purchase.purchase_date)
            if day:
                trend[day.isoformat()]["quantity"] += self._to_float(item.qty)
        subtotal = sum(self._to_float(p.subtotal) for p in matched_purchases)
        return {
            "from_date": filters.from_date.isoformat(),
            "to_date": filters.to_date.isoformat(),
            "purchases_count": len(matched_purchases),
            "purchases_subtotal": subtotal,
            "purchases_trend": [
                {"period": period, "subtotal": row["subtotal"], "quantity": row["quantity"]}
                for period, row in sorted(trend.items(), key=lambda x: x[0])
            ],
            "deferred_metrics": [],
        }

    def overview_report(self, *, client_id: str, filters: ReportFilters) -> dict[str, object]:
        sales = self.sales_report(client_id=client_id, filters=filters)
        finance = self.finance_report(client_id=client_id, filters=filters)
        returns = self.returns_report(client_id=client_id, filters=filters)
        purchases = self.purchases_report(client_id=client_id, filters=filters)
        return {
            "from_date": filters.from_date.isoformat(),
            "to_date": filters.to_date.isoformat(),
            "sales_revenue_total": sales["revenue_total"],
            "sales_count": sales["sales_count"],
            "expense_total": finance["expense_total"],
            "returns_total": returns["return_amount_total"],
            "purchases_total": purchases["purchases_subtotal"],
        }

