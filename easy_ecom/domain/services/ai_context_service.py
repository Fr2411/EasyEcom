from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.data.store.postgres_models import (
    CustomerModel,
    InventoryTxnModel,
    ProductModel,
    ProductVariantModel,
    SalesOrderItemModel,
    SalesOrderModel,
    TenantSettingsModel,
)


@dataclass(frozen=True)
class InquiryPayload:
    message: str
    customer_ref: str | None = None


class AiContextService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    @staticmethod
    def _to_float(value: str | float | int | None) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _day(raw: str) -> datetime | None:
        if not raw:
            return None
        compact = raw.strip()
        try:
            return datetime.fromisoformat(compact.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.strptime(compact[:10], "%Y-%m-%d")
            except ValueError:
                return None

    def _fetch_tenant_data(self, client_id: str) -> dict[str, list[object]]:
        with self.session_factory() as session:
            products = session.execute(
                select(ProductModel).where(ProductModel.client_id == client_id)
            ).scalars().all()
            variants = session.execute(
                select(ProductVariantModel).where(ProductVariantModel.client_id == client_id)
            ).scalars().all()
            txns = session.execute(
                select(InventoryTxnModel).where(InventoryTxnModel.client_id == client_id)
            ).scalars().all()
            orders = session.execute(
                select(SalesOrderModel).where(SalesOrderModel.client_id == client_id)
            ).scalars().all()
            order_items = session.execute(
                select(SalesOrderItemModel).where(SalesOrderItemModel.client_id == client_id)
            ).scalars().all()
            customers = session.execute(
                select(CustomerModel).where(CustomerModel.client_id == client_id)
            ).scalars().all()
            settings = session.execute(
                select(TenantSettingsModel).where(TenantSettingsModel.client_id == client_id)
            ).scalar_one_or_none()

        return {
            "products": products,
            "variants": variants,
            "txns": txns,
            "orders": orders,
            "order_items": order_items,
            "customers": customers,
            "settings": [settings] if settings else [],
        }

    def _stock_by_product(self, txns: list[InventoryTxnModel]) -> dict[str, float]:
        balances: dict[str, float] = defaultdict(float)
        for txn in txns:
            qty = self._to_float(txn.qty)
            balances[txn.product_id] += qty if txn.txn_type in {"IN", "ADJUST", "ADJUST+"} else -qty
        return balances

    def overview(self, *, client_id: str) -> dict[str, object]:
        data = self._fetch_tenant_data(client_id)
        stock = self._stock_by_product(data["txns"])
        confirmed_orders = [o for o in data["orders"] if o.status == "confirmed"]
        revenue = sum(self._to_float(o.grand_total) for o in confirmed_orders)
        low_threshold = 5
        if data["settings"]:
            try:
                low_threshold = max(0, int((data["settings"][0].low_stock_threshold or "5").strip()))
            except ValueError:
                low_threshold = 5

        low_stock_count = 0
        for product in data["products"]:
            qty = stock.get(product.product_id, 0.0)
            if qty <= low_threshold:
                low_stock_count += 1

        return {
            "tenant_id": client_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "products_count": len(data["products"]),
            "variants_count": len(data["variants"]),
            "active_customers_count": sum(1 for c in data["customers"] if (c.is_active or "true") == "true"),
            "confirmed_sales_count": len(confirmed_orders),
            "confirmed_sales_revenue": revenue,
            "low_stock_items_count": low_stock_count,
            "domains": [
                "products",
                "stock",
                "pricing",
                "sales",
                "customers",
                "recent_activity",
            ],
            "deferred_capabilities": [
                "No external channel (WhatsApp/Messenger) delivery in this phase.",
                "No free-form natural-language-to-SQL execution.",
            ],
        }

    def products_context(self, *, client_id: str, query: str = "", limit: int = 20) -> dict[str, object]:
        data = self._fetch_tenant_data(client_id)
        stock = self._stock_by_product(data["txns"])
        variants_by_product: dict[str, list[ProductVariantModel]] = defaultdict(list)
        for variant in data["variants"]:
            variants_by_product[variant.parent_product_id].append(variant)

        needle = query.strip().lower()
        rows: list[dict[str, object]] = []
        for product in data["products"]:
            if needle and needle not in product.product_name.lower() and needle not in product.product_id.lower():
                continue
            rows.append(
                {
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "category": product.category,
                    "default_price": self._to_float(product.default_selling_price),
                    "stock_qty": stock.get(product.product_id, 0.0),
                    "variants": [
                        {
                            "variant_id": variant.variant_id,
                            "variant_name": variant.variant_name,
                            "sku_code": variant.sku_code,
                            "default_price": self._to_float(variant.default_selling_price),
                            "is_active": (variant.is_active or "true") == "true",
                        }
                        for variant in variants_by_product.get(product.product_id, [])[:10]
                    ],
                }
            )
            if len(rows) >= limit:
                break

        return {"query": needle, "count": len(rows), "items": rows}

    def stock_context(self, *, client_id: str, product_id: str = "") -> dict[str, object]:
        data = self._fetch_tenant_data(client_id)
        stock = self._stock_by_product(data["txns"])
        rows = []
        target = product_id.strip()
        for product in data["products"]:
            if target and product.product_id != target:
                continue
            rows.append(
                {
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "available_qty": stock.get(product.product_id, 0.0),
                }
            )
        return {"product_id": target or None, "count": len(rows), "items": rows[:50]}

    def low_stock_context(self, *, client_id: str, threshold: int | None = None) -> dict[str, object]:
        data = self._fetch_tenant_data(client_id)
        stock = self._stock_by_product(data["txns"])
        effective_threshold = 5 if threshold is None else max(0, threshold)
        items = []
        for product in data["products"]:
            qty = stock.get(product.product_id, 0.0)
            if qty <= effective_threshold:
                items.append({"product_id": product.product_id, "product_name": product.product_name, "available_qty": qty})
        items.sort(key=lambda row: row["available_qty"])
        return {"threshold": effective_threshold, "count": len(items), "items": items[:50]}

    def sales_context(self, *, client_id: str, days: int = 7) -> dict[str, object]:
        data = self._fetch_tenant_data(client_id)
        since = datetime.now(UTC) - timedelta(days=max(1, min(days, 90)))
        orders = [o for o in data["orders"] if o.status == "confirmed" and (self._day(o.timestamp) or since) >= since]
        order_ids = {o.order_id for o in orders}

        top_products: dict[str, dict[str, float | str]] = defaultdict(
            lambda: {"product_name": "", "qty_sold": 0.0, "revenue": 0.0}
        )
        for item in data["order_items"]:
            if item.order_id not in order_ids:
                continue
            entry = top_products[item.product_id]
            entry["product_name"] = item.product_name_snapshot or item.product_id
            entry["qty_sold"] = float(entry["qty_sold"]) + self._to_float(item.qty)
            entry["revenue"] = float(entry["revenue"]) + self._to_float(item.total_selling_price)

        ranked = sorted(
            [
                {
                    "product_id": pid,
                    "product_name": str(values["product_name"]),
                    "qty_sold": float(values["qty_sold"]),
                    "revenue": float(values["revenue"]),
                }
                for pid, values in top_products.items()
            ],
            key=lambda row: (row["qty_sold"], row["revenue"]),
            reverse=True,
        )[:10]

        return {
            "window_days": max(1, min(days, 90)),
            "confirmed_sales_count": len(orders),
            "confirmed_sales_revenue": sum(self._to_float(o.grand_total) for o in orders),
            "top_products": ranked,
        }

    def customers_context(self, *, client_id: str, query: str = "") -> dict[str, object]:
        data = self._fetch_tenant_data(client_id)
        needle = query.strip().lower()
        customers = []
        for customer in data["customers"]:
            match = not needle or needle in customer.full_name.lower() or needle in (customer.phone or "").lower()
            if not match:
                continue
            customers.append(
                {
                    "customer_id": customer.customer_id,
                    "full_name": customer.full_name,
                    "phone": customer.phone,
                    "email": customer.email,
                    "is_active": (customer.is_active or "true") == "true",
                }
            )
        return {"query": needle, "count": len(customers), "items": customers[:25]}

    def lookup_context(self, *, client_id: str, kind: str, query: str) -> dict[str, object]:
        compact_query = query.strip().lower()
        if not compact_query:
            raise ValueError("query is required")

        if kind == "product":
            return self.products_context(client_id=client_id, query=compact_query, limit=10)
        if kind == "customer":
            return self.customers_context(client_id=client_id, query=compact_query)
        if kind == "sale":
            data = self._fetch_tenant_data(client_id)
            hits = []
            for order in data["orders"]:
                if compact_query not in order.sale_no.lower() and compact_query not in order.order_id.lower():
                    continue
                hits.append(
                    {
                        "sale_id": order.order_id,
                        "sale_no": order.sale_no,
                        "status": order.status,
                        "timestamp": order.timestamp,
                        "grand_total": self._to_float(order.grand_total),
                        "payment_status": order.payment_status,
                    }
                )
            return {"query": compact_query, "count": len(hits), "items": hits[:15]}
        raise ValueError("Unsupported lookup kind")

    def recent_activity_context(self, *, client_id: str, days: int = 7) -> dict[str, object]:
        data = self._fetch_tenant_data(client_id)
        since = datetime.now(UTC) - timedelta(days=max(1, min(days, 30)))
        inventory_events = []
        for txn in data["txns"]:
            event_at = self._day(txn.timestamp)
            if not event_at or event_at < since:
                continue
            inventory_events.append(
                {
                    "type": "inventory",
                    "timestamp": txn.timestamp,
                    "reference_id": txn.txn_id,
                    "summary": f"{txn.txn_type} {txn.qty} for {txn.product_name or txn.product_id}",
                }
            )
        sale_events = []
        for order in data["orders"]:
            event_at = self._day(order.timestamp)
            if not event_at or event_at < since:
                continue
            sale_events.append(
                {
                    "type": "sale",
                    "timestamp": order.timestamp,
                    "reference_id": order.order_id,
                    "summary": f"{order.sale_no or order.order_id} {order.status} total {order.grand_total}",
                }
            )
        items = sorted(inventory_events + sale_events, key=lambda row: row["timestamp"], reverse=True)[:30]
        return {"window_days": max(1, min(days, 30)), "count": len(items), "items": items}

    def handle_inbound_inquiry(self, *, client_id: str, payload: InquiryPayload) -> dict[str, object]:
        message = payload.message.strip().lower()
        if not message:
            raise ValueError("message is required")

        if "stock" in message or "available" in message:
            intent = "stock_check"
            context = self.stock_context(client_id=client_id)
            suggested_endpoint = "/ai/context/stock"
        elif "price" in message or "cost" in message:
            intent = "pricing_lookup"
            context = self.products_context(client_id=client_id, limit=5)
            suggested_endpoint = "/ai/context/products"
        elif "order" in message or "sale" in message:
            intent = "order_lookup"
            context = self.sales_context(client_id=client_id, days=7)
            suggested_endpoint = "/ai/context/sales"
        else:
            intent = "business_summary"
            context = self.overview(client_id=client_id)
            suggested_endpoint = "/ai/context/overview"

        return {
            "intent": intent,
            "suggested_endpoint": suggested_endpoint,
            "customer_ref": payload.customer_ref,
            "context": context,
            "guardrails": {
                "tenant_scoped": True,
                "read_only": True,
                "llm_direct_db_access": False,
            },
        }
