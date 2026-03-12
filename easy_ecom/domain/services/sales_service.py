from __future__ import annotations

import json

import pandas as pd

from easy_ecom.core.audit import log_event
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.repos.csv.audit_repo import AuditRepo
from easy_ecom.data.repos.csv.customers_repo import CustomersRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, PaymentsRepo, SalesOrderItemsRepo, SalesOrdersRepo, ShipmentsRepo
from easy_ecom.domain.models.sales import SaleConfirm, SaleItem
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService


class SalesService:
    """Order lifecycle service.

    Stock rule: validate stock on place/confirm and deduct when order is confirmed.
    """

    ORDER_STATUSES = {"draft", "placed", "confirmed", "cancelled", "closed"}

    def __init__(
        self,
        orders_repo: SalesOrdersRepo,
        items_repo: SalesOrderItemsRepo,
        invoices_repo: InvoicesRepo,
        shipments_repo: ShipmentsRepo,
        payments_repo: PaymentsRepo,
        inv_service: InventoryService,
        seq_service: SequenceService,
        finance_service: FinanceService,
        products_repo: ProductsRepo,
        customers_repo: CustomersRepo | None = None,
        audit_repo: AuditRepo | None = None,
        variants_repo: ProductVariantsRepo | None = None,
    ):
        self.orders_repo = orders_repo
        self.items_repo = items_repo
        self.invoices_repo = invoices_repo
        self.shipments_repo = shipments_repo
        self.payments_repo = payments_repo
        self.inv_service = inv_service
        self.seq_service = seq_service
        self.finance_service = finance_service
        self.products_repo = products_repo
        self.customers_repo = customers_repo
        self.audit_repo = audit_repo
        self.variants_repo = variants_repo

    @staticmethod
    def _to_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalize_orders(self) -> pd.DataFrame:
        orders = self.orders_repo.all()
        if orders.empty:
            return orders
        defaults = {
            "order_status": "",
            "payment_status": "",
            "fulfillment_status": "",
            "return_status": "",
            "amount_paid": "0",
            "amount_refunded": "0",
            "balance_due": "0",
            "pricing_locked_at": "",
            "customer_snapshot_json": "",
            "delivery_cost": "0",
            "delivery_provider": "",
            "discount": "0",
            "tax": "0",
            "subtotal": "0",
            "grand_total": "0",
        }
        for col, default in defaults.items():
            if col not in orders.columns:
                orders[col] = default
        for i, row in orders.iterrows():
            legacy_status = str(row.get("status", "")).strip().lower() or "draft"
            mapped_order = legacy_status if legacy_status in self.ORDER_STATUSES else ("confirmed" if legacy_status == "confirmed" else "draft")
            orders.loc[i, "order_status"] = str(row.get("order_status", "") or mapped_order)
            orders.loc[i, "status"] = orders.loc[i, "order_status"]
            orders.loc[i, "payment_status"] = str(row.get("payment_status", "") or "unpaid")
            orders.loc[i, "fulfillment_status"] = str(row.get("fulfillment_status", "") or ("delivered" if mapped_order == "closed" else "unfulfilled"))
            orders.loc[i, "return_status"] = str(row.get("return_status", "") or "none")
            grand_total = max(0.0, self._to_float(row.get("grand_total", 0)))
            amount_paid = max(0.0, self._to_float(row.get("amount_paid", 0)))
            amount_refunded = max(0.0, self._to_float(row.get("amount_refunded", 0)))
            orders.loc[i, "amount_paid"] = str(amount_paid)
            orders.loc[i, "amount_refunded"] = str(amount_refunded)
            orders.loc[i, "balance_due"] = str(max(0.0, grand_total - amount_paid + amount_refunded))
        self.orders_repo.save(orders)
        return orders

    def _normalize_invoices(self) -> pd.DataFrame:
        invoices = self.invoices_repo.all()
        if invoices.empty:
            return invoices
        for col, default in {
            "subtotal": "0",
            "discount": "0",
            "tax": "0",
            "delivery_cost": "0",
            "grand_total": "0",
            "amount_paid": "0",
            "amount_refunded": "0",
            "customer_snapshot_json": "",
            "line_items_json": "[]",
        }.items():
            if col not in invoices.columns:
                invoices[col] = default
        self.invoices_repo.save(invoices)
        return invoices

    def _normalize_shipments(self) -> pd.DataFrame:
        shipments = self.shipments_repo.all()
        if shipments.empty:
            return shipments
        for col, default in {
            "shipped_at": "",
            "delivery_cost_snapshot": "0",
            "carrier": "",
            "note": "",
        }.items():
            if col not in shipments.columns:
                shipments[col] = default
        self.shipments_repo.save(shipments)
        return shipments

    def _get_order_idx(self, order_id: str, client_id: str | None = None) -> tuple[pd.DataFrame, int]:
        orders = self._normalize_orders()
        if orders.empty:
            raise ValueError("Order not found")
        scoped = orders[orders["order_id"] == order_id]
        if client_id:
            scoped = scoped[scoped["client_id"] == client_id]
        if scoped.empty:
            raise ValueError("Order not found")
        return orders, int(scoped.index[0])

    def _ensure_invoice_for_order(self, order: dict[str, str]) -> dict[str, str]:
        self._normalize_invoices()
        invoices = self.invoices_repo.all()
        existing = invoices[invoices["order_id"] == order["order_id"]] if not invoices.empty else pd.DataFrame()
        totals = self.compute_order_totals(order["order_id"])
        if not existing.empty:
            invoice = existing.iloc[0].to_dict()
            self.compute_invoice_balance(order["order_id"])
            return invoice

        year = pd.Timestamp.utcnow().year
        invoice_id = new_uuid()
        invoice_no = self.seq_service.next(order["client_id"], "INVOICE", year, "INV")
        customer = self.customers_repo.get(str(order.get("customer_id", ""))) if self.customers_repo else {}
        line_items = self.get_order_items(order["order_id"]).to_dict(orient="records")
        self.invoices_repo.append(
            {
                "invoice_id": invoice_id,
                "client_id": order["client_id"],
                "invoice_no": invoice_no,
                "order_id": order["order_id"],
                "customer_id": order.get("customer_id", ""),
                "timestamp": now_iso(),
                "subtotal": str(totals["subtotal"]),
                "discount": str(totals["discount"]),
                "tax": str(totals["tax"]),
                "delivery_cost": str(totals["delivery_cost"]),
                "grand_total": str(totals["grand_total"]),
                "amount_paid": str(self._to_float(order.get("amount_paid", 0))),
                "amount_refunded": str(self._to_float(order.get("amount_refunded", 0))),
                "amount_due": str(self._to_float(order.get("balance_due", totals["grand_total"]))),
                "status": str(order.get("payment_status", "unpaid")),
                "customer_snapshot_json": json.dumps(customer or {}),
                "line_items_json": json.dumps(line_items),
            }
        )
        return {"invoice_id": invoice_id, "invoice_no": invoice_no}

    def create_draft_order(
        self,
        client_id: str,
        customer_id: str,
        note: str = "",
        delivery_provider: str = "",
        delivery_cost: float = 0.0,
        discount: float = 0.0,
        tax: float = 0.0,
    ) -> str:
        order_id = new_uuid()
        self.orders_repo.append(
            {
                "order_id": order_id,
                "client_id": client_id,
                "timestamp": now_iso(),
                "customer_id": customer_id,
                "status": "draft",
                "order_status": "draft",
                "payment_status": "unpaid",
                "fulfillment_status": "unfulfilled",
                "return_status": "none",
                "subtotal": "0",
                "discount": str(max(0.0, discount)),
                "tax": str(max(0.0, tax)),
                "delivery_cost": str(max(0.0, delivery_cost)),
                "grand_total": str(max(0.0, -discount + tax + delivery_cost)),
                "amount_paid": "0",
                "amount_refunded": "0",
                "balance_due": str(max(0.0, -discount + tax + delivery_cost)),
                "pricing_locked_at": "",
                "customer_snapshot_json": "",
                "delivery_provider": delivery_provider,
                "note": note,
            }
        )
        return order_id

    def get_or_create_customer_draft(self, client_id: str, customer_id: str, force_new: bool = False) -> str:
        orders = self._normalize_orders()
        if not force_new and not orders.empty:
            matched = orders[(orders["client_id"] == client_id) & (orders["customer_id"] == customer_id) & (orders["order_status"] == "draft")].copy()
            if not matched.empty:
                matched["timestamp"] = pd.to_datetime(matched["timestamp"], errors="coerce")
                return str(matched.sort_values("timestamp", ascending=False).iloc[0]["order_id"])
        return self.create_draft_order(client_id, customer_id)

    def get_order(self, order_id: str) -> dict[str, str] | None:
        orders = self._normalize_orders()
        if orders.empty:
            return None
        found = orders[orders["order_id"] == order_id]
        return found.iloc[0].to_dict() if not found.empty else None

    def get_order_items(self, order_id: str) -> pd.DataFrame:
        items = self.items_repo.all()
        if items.empty:
            return pd.DataFrame(columns=["order_item_id", "order_id", "product_id", "prd_description_snapshot", "qty", "unit_selling_price", "total_selling_price"])
        return items[items["order_id"] == order_id].copy()

    def compute_order_totals(self, order_id: str) -> dict[str, float]:
        order = self.get_order(order_id) or {}
        discount = max(0.0, self._to_float(order.get("discount", 0)))
        tax = max(0.0, self._to_float(order.get("tax", 0)))
        delivery_cost = max(0.0, self._to_float(order.get("delivery_cost", 0)))
        items = self.get_order_items(order_id)
        subtotal = 0.0 if items.empty else float((items["qty"].astype(float) * items["unit_selling_price"].astype(float)).sum())
        grand_total = max(0.0, subtotal - discount + tax + delivery_cost)
        return {
            "item_count": int(items["qty"].astype(float).sum()) if not items.empty else 0,
            "subtotal": subtotal,
            "discount": discount,
            "tax": tax,
            "delivery_cost": delivery_cost,
            "grand_total": grand_total,
        }

    def recalculate_order_totals(self, order_id: str) -> dict[str, float]:
        totals = self.compute_order_totals(order_id)
        orders, idx = self._get_order_idx(order_id)
        paid = self._to_float(orders.loc[idx, "amount_paid"], 0)
        refunded = self._to_float(orders.loc[idx, "amount_refunded"], 0)
        orders.loc[idx, "subtotal"] = str(totals["subtotal"])
        orders.loc[idx, "discount"] = str(totals["discount"])
        orders.loc[idx, "tax"] = str(totals["tax"])
        orders.loc[idx, "delivery_cost"] = str(totals["delivery_cost"])
        orders.loc[idx, "grand_total"] = str(totals["grand_total"])
        orders.loc[idx, "balance_due"] = str(max(0.0, totals["grand_total"] - paid + refunded))
        self.orders_repo.save(orders)
        self.compute_invoice_balance(order_id)
        return totals

    def compute_invoice_balance(self, order_id: str) -> dict[str, float]:
        self._normalize_invoices()
        orders = self._normalize_orders()
        scoped = orders[orders["order_id"] == order_id]
        if scoped.empty:
            return {"amount_paid": 0.0, "amount_refunded": 0.0, "balance_due": 0.0}
        order = scoped.iloc[0]
        payments = self.payments_repo.all()
        successful = payments[(payments.get("order_id", "") == order_id) | (payments.get("invoice_id", "") == order.get("invoice_id", ""))] if not payments.empty else pd.DataFrame()
        if not successful.empty:
            if "status" not in successful.columns:
                successful["status"] = "successful"
            successful = successful[successful["status"].isin(["", "successful"])]
            paid = float(successful["amount_paid"].astype(float).sum())
        else:
            paid = self._to_float(order.get("amount_paid", 0))
        refunded = max(0.0, self._to_float(order.get("amount_refunded", 0)))
        grand_total = max(0.0, self._to_float(order.get("grand_total", 0)))
        balance_due = max(0.0, grand_total - paid + refunded)
        if paid <= 0:
            payment_status = "unpaid"
            invoice_status = "unpaid"
        elif paid < grand_total:
            payment_status = "partially_paid"
            invoice_status = "partially_paid"
        elif refunded > 0 and refunded < paid:
            payment_status = "partially_refunded"
            invoice_status = "partially_refunded"
        elif refunded >= paid and paid > 0:
            payment_status = "refunded"
            invoice_status = "refunded"
        else:
            payment_status = "paid"
            invoice_status = "paid"

        idx = scoped.index[0]
        orders.loc[idx, "amount_paid"] = str(paid)
        orders.loc[idx, "balance_due"] = str(balance_due)
        orders.loc[idx, "payment_status"] = payment_status
        self.orders_repo.save(orders)

        invoices = self.invoices_repo.all()
        if not invoices.empty:
            iv = invoices[invoices["order_id"] == order_id]
            if not iv.empty:
                ii = iv.index[0]
                invoices.loc[ii, "amount_paid"] = str(paid)
                invoices.loc[ii, "amount_refunded"] = str(refunded)
                invoices.loc[ii, "amount_due"] = str(balance_due)
                invoices.loc[ii, "status"] = invoice_status
                self.invoices_repo.save(invoices)
        return {"amount_paid": paid, "amount_refunded": refunded, "balance_due": balance_due}

    def update_order_pricing(self, order_id: str, client_id: str, discount: float, tax: float, delivery_cost: float, delivery_provider: str, note: str) -> dict[str, float]:
        orders, idx = self._get_order_idx(order_id, client_id)
        if orders.loc[idx, "order_status"] != "draft":
            raise ValueError("Commercial values can only be edited while draft")
        orders.loc[idx, "discount"] = str(max(0.0, float(discount)))
        orders.loc[idx, "tax"] = str(max(0.0, float(tax)))
        orders.loc[idx, "delivery_cost"] = str(max(0.0, float(delivery_cost)))
        orders.loc[idx, "delivery_provider"] = str(delivery_provider or "")
        orders.loc[idx, "note"] = str(note or "")
        self.orders_repo.save(orders)
        return self.recalculate_order_totals(order_id)

    def empty_draft_order(self, order_id: str, client_id: str) -> None:
        orders, idx = self._get_order_idx(order_id, client_id)
        if orders.loc[idx, "order_status"] != "draft":
            raise ValueError("Only draft orders can be edited")
        items = self.items_repo.all()
        if items.empty:
            return
        self.items_repo.save(items[items["order_id"] != order_id].reset_index(drop=True))
        self.recalculate_order_totals(order_id)

    def min_allowed_price(self, client_id: str, product_id: str) -> float:
        products = self.products_repo.all()
        variants = self.variants_repo.all() if self.variants_repo is not None else pd.DataFrame()
        if not variants.empty:
            v = variants[(variants["client_id"] == client_id) & (variants["variant_id"] == product_id)]
            if not v.empty:
                row = v.iloc[0]
                base = self._to_float(row.get("default_selling_price", 0.0))
                max_discount = self._to_float(row.get("max_discount_pct", 0.0))
                return max(0.0, base * (1 - max_discount / 100.0))
        p = products[(products["client_id"] == client_id) & (products["product_id"] == product_id)]
        if p.empty:
            raise ValueError("Product not found")
        row = p.iloc[0]
        base = self._to_float(row.get("default_selling_price", 0.0))
        max_discount = self._to_float(row.get("max_discount_pct", 0.0))
        return max(0.0, base * (1 - max_discount / 100.0))

    def validate_item_pricing(self, client_id: str, item: SaleItem) -> None:
        min_price = self.min_allowed_price(client_id, item.product_id)
        if item.unit_selling_price < min_price:
            raise ValueError(f"Unit price {item.unit_selling_price} is below minimum allowed {min_price:.2f}")

    def add_item_to_draft(self, order_id: str, client_id: str, item: SaleItem) -> str:
        orders, idx = self._get_order_idx(order_id, client_id)
        if orders.loc[idx, "order_status"] != "draft":
            raise ValueError("Only draft orders can be edited")
        self.validate_item_pricing(client_id, item)
        items = self.items_repo.all()
        if not items.empty:
            matched = items[(items["order_id"] == order_id) & (items["product_id"] == item.product_id) & (items["unit_selling_price"].astype(float) == float(item.unit_selling_price))]
            if not matched.empty:
                line_idx = matched.index[0]
                qty = self._to_float(items.loc[line_idx, "qty"]) + float(item.qty)
                items.loc[line_idx, "qty"] = str(qty)
                items.loc[line_idx, "total_selling_price"] = str(qty * float(item.unit_selling_price))
                self.items_repo.save(items)
                self.recalculate_order_totals(order_id)
                return str(items.loc[line_idx, "order_item_id"])
        order_item_id = new_uuid()
        self.items_repo.append({"order_item_id": order_item_id, "order_id": order_id, "product_id": item.product_id, "prd_description_snapshot": "", "qty": str(item.qty), "unit_selling_price": str(item.unit_selling_price), "total_selling_price": str(item.qty * item.unit_selling_price)})
        self.recalculate_order_totals(order_id)
        return order_item_id

    def update_draft_item(self, order_item_id: str, qty: float, unit_price: float, client_id: str) -> None:
        items = self.items_repo.all()
        idx = items[items["order_item_id"] == order_item_id].index
        if len(idx) == 0:
            raise ValueError("Order item not found")
        i = idx[0]
        order_id = str(items.loc[i, "order_id"])
        order = self.get_order(order_id) or {}
        if order.get("client_id") != client_id or order.get("order_status") != "draft":
            raise ValueError("Only draft orders can be edited")
        item = SaleItem(product_id=str(items.loc[i, "product_id"]), qty=qty, unit_selling_price=unit_price)
        self.validate_item_pricing(client_id, item)
        items.loc[i, "qty"] = str(qty)
        items.loc[i, "unit_selling_price"] = str(unit_price)
        items.loc[i, "total_selling_price"] = str(qty * unit_price)
        self.items_repo.save(items)
        self.recalculate_order_totals(order_id)

    def remove_draft_item(self, order_item_id: str, client_id: str) -> None:
        items = self.items_repo.all()
        idx = items[items["order_item_id"] == order_item_id].index
        if len(idx) == 0:
            return
        order_id = str(items.loc[idx[0], "order_id"])
        order = self.get_order(order_id) or {}
        if order.get("client_id") != client_id or order.get("order_status") != "draft":
            raise ValueError("Only draft orders can be edited")
        self.items_repo.save(items.drop(index=idx[0]).reset_index(drop=True))
        self.recalculate_order_totals(order_id)

    def list_draft_orders(self, client_id: str) -> pd.DataFrame:
        orders = self._normalize_orders()
        if orders.empty:
            return orders
        drafts = orders[(orders["client_id"] == client_id) & (orders["order_status"] == "draft")].copy()
        if drafts.empty:
            return drafts
        counts = self.items_repo.all().groupby("order_id", as_index=False).size().rename(columns={"size": "item_count"}) if not self.items_repo.all().empty else pd.DataFrame(columns=["order_id", "item_count"])
        return drafts.merge(counts, on="order_id", how="left").fillna({"item_count": 0})

    def place_order_from_draft(self, order_id: str, user_ctx: dict[str, str]) -> dict[str, str]:
        orders, idx = self._get_order_idx(order_id)
        order = orders.loc[idx].to_dict()
        if order.get("order_status") != "draft":
            raise ValueError("Only draft orders can be placed")
        items = self.get_order_items(order_id)
        if items.empty:
            raise ValueError("Draft order has no items")
        for row in items.itertuples(index=False):
            self.inv_service.allocate_fifo(order["client_id"], str(row.product_id), float(row.qty))
            self.validate_item_pricing(order["client_id"], SaleItem(product_id=str(row.product_id), qty=float(row.qty), unit_selling_price=float(row.unit_selling_price)))
        totals = self.recalculate_order_totals(order_id)
        customer = self.customers_repo.get(str(order.get("customer_id", ""))) if self.customers_repo else {}
        orders.loc[idx, "order_status"] = "placed"
        orders.loc[idx, "status"] = "placed"
        orders.loc[idx, "pricing_locked_at"] = now_iso()
        orders.loc[idx, "customer_snapshot_json"] = json.dumps(customer or {})
        self.orders_repo.save(orders)
        invoice = self._ensure_invoice_for_order({**order, "order_id": order_id})
        return {"order_id": order_id, "invoice_id": invoice.get("invoice_id", ""), "invoice_no": invoice.get("invoice_no", "")}

    def confirm_order(self, order_id: str, user_ctx: dict[str, str]) -> dict[str, str]:
        orders, idx = self._get_order_idx(order_id, user_ctx.get("client_id"))
        order = orders.loc[idx].to_dict()
        if order.get("order_status") == "draft":
            self.place_order_from_draft(order_id, user_ctx)
            orders, idx = self._get_order_idx(order_id, user_ctx.get("client_id"))
            order = orders.loc[idx].to_dict()
        if order.get("order_status") != "placed":
            raise ValueError("Only placed orders can be confirmed")
        items = self.get_order_items(order_id)
        for row in items.itertuples(index=False):
            self.inv_service.deduct_stock(order["client_id"], str(row.product_id), str(row.product_id), float(row.qty), "sale", order_id, user_id=user_ctx.get("user_id", ""))
        totals = self.compute_order_totals(order_id)
        orders.loc[idx, "order_status"] = "confirmed"
        orders.loc[idx, "status"] = "confirmed"
        orders.loc[idx, "balance_due"] = str(max(0.0, totals["grand_total"] - self._to_float(orders.loc[idx, "amount_paid"]) + self._to_float(orders.loc[idx, "amount_refunded"])))
        self.orders_repo.save(orders)
        invoice = self._ensure_invoice_for_order(order)
        self.compute_invoice_balance(order_id)
        self.finance_service.add_entry(order["client_id"], "earning", "Sales", totals["grand_total"], "sale", invoice.get("invoice_id", ""), "Order confirmed sale posted", user_id=user_ctx.get("user_id", ""))
        return {"order_id": order_id, "invoice_id": invoice.get("invoice_id", ""), "invoice_no": invoice.get("invoice_no", "")}

    def mark_ready_to_pack(self, order_id: str, user_ctx: dict[str, str]) -> None:
        orders, idx = self._get_order_idx(order_id, user_ctx.get("client_id"))
        if orders.loc[idx, "order_status"] not in ["placed", "confirmed"]:
            raise ValueError("Only placed/confirmed orders can be packed")
        if orders.loc[idx, "order_status"] == "placed":
            self.confirm_order(order_id, user_ctx)
            orders, idx = self._get_order_idx(order_id, user_ctx.get("client_id"))
        orders.loc[idx, "fulfillment_status"] = "ready_to_pack"
        self.orders_repo.save(orders)

    def mark_packed(self, order_id: str, user_ctx: dict[str, str]) -> None:
        orders, idx = self._get_order_idx(order_id, user_ctx.get("client_id"))
        if orders.loc[idx, "fulfillment_status"] not in ["ready_to_pack", "unfulfilled"]:
            raise ValueError("Order is not ready to be packed")
        orders.loc[idx, "fulfillment_status"] = "packed"
        self.orders_repo.save(orders)

    def create_shipment_for_order(self, order_id: str, shipment_payload: dict[str, str], user_ctx: dict[str, str]) -> dict[str, str]:
        self._normalize_shipments()
        orders, idx = self._get_order_idx(order_id, user_ctx.get("client_id"))
        order = orders.loc[idx]
        if order["order_status"] in ["draft", "cancelled"]:
            raise ValueError("Shipment cannot be created in current order state")
        shipments = self.shipments_repo.all()
        existing = shipments[(shipments["order_id"] == order_id) & (shipments["client_id"] == order["client_id"])] if not shipments.empty else pd.DataFrame()
        if not existing.empty:
            raise ValueError("Shipment already exists; split shipments are not supported yet")
        if order["fulfillment_status"] not in ["packed", "ready_to_pack", "unfulfilled"]:
            raise ValueError("Order is not eligible for shipment")
        year = pd.Timestamp.utcnow().year
        shipment_id = new_uuid()
        shipment_no = self.seq_service.next(order["client_id"], "SHIPMENT", year, "SHP")
        customer = self.customers_repo.get(str(order.get("customer_id", ""))) if self.customers_repo else {}
        self.shipments_repo.append({
            "shipment_id": shipment_id,
            "client_id": order["client_id"],
            "shipment_no": shipment_no,
            "order_id": order_id,
            "customer_id": order.get("customer_id", ""),
            "timestamp": now_iso(),
            "status": "shipped",
            "shipped_at": shipment_payload.get("shipped_at") or now_iso(),
            "delivery_cost_snapshot": str(self._to_float(order.get("delivery_cost", 0))),
            "ship_to_name_snapshot": (customer or {}).get("full_name", ""),
            "ship_to_phone_snapshot": (customer or {}).get("phone", ""),
            "ship_to_address_snapshot": (customer or {}).get("address_line1", ""),
            "carrier": shipment_payload.get("carrier", ""),
            "courier": shipment_payload.get("carrier", ""),
            "tracking_no": shipment_payload.get("tracking_no", ""),
            "note": shipment_payload.get("note", ""),
        })
        orders.loc[idx, "fulfillment_status"] = "shipped"
        self.orders_repo.save(orders)
        return {"shipment_id": shipment_id, "shipment_no": shipment_no}

    def mark_delivered(self, order_id: str, user_ctx: dict[str, str]) -> None:
        orders, idx = self._get_order_idx(order_id, user_ctx.get("client_id"))
        if orders.loc[idx, "fulfillment_status"] != "shipped":
            raise ValueError("Only shipped orders can be delivered")
        orders.loc[idx, "fulfillment_status"] = "delivered"
        if orders.loc[idx, "payment_status"] in ["paid", "refunded"]:
            orders.loc[idx, "order_status"] = "closed"
            orders.loc[idx, "status"] = "closed"
        self.orders_repo.save(orders)

    def mark_delivery_failed(self, order_id: str, reason: str, user_ctx: dict[str, str]) -> None:
        orders, idx = self._get_order_idx(order_id, user_ctx.get("client_id"))
        if orders.loc[idx, "fulfillment_status"] != "shipped":
            raise ValueError("Only shipped orders can be marked failed")
        orders.loc[idx, "fulfillment_status"] = "delivery_failed"
        orders.loc[idx, "note"] = f"{orders.loc[idx, 'note']}\nDelivery failure: {reason}".strip()
        self.orders_repo.save(orders)

    def cancel_order(self, order_id: str, reason: str, user_ctx: dict[str, str]) -> None:
        orders, idx = self._get_order_idx(order_id, user_ctx.get("client_id"))
        if orders.loc[idx, "order_status"] in ["closed", "cancelled"]:
            raise ValueError("Order is already finalised")
        if self._to_float(orders.loc[idx, "amount_paid"], 0) > 0:
            raise ValueError("Cannot cancel paid order without refund workflow")
        orders.loc[idx, "order_status"] = "cancelled"
        orders.loc[idx, "status"] = "cancelled"
        orders.loc[idx, "note"] = f"{orders.loc[idx, 'note']}\nCancelled: {reason}".strip()
        self.orders_repo.save(orders)

    def cancel_draft_order(self, order_id: str) -> bool:
        try:
            self.cancel_order(order_id, "Cancelled draft", {})
            return True
        except Exception:
            return False

    def resolve_order_items(self, client_id: str, order_id: str) -> pd.DataFrame:
        items = self.get_order_items(order_id)
        if items.empty:
            return pd.DataFrame(columns=["order_item_id", "order_id", "product_id", "qty", "unit_selling_price", "line_total", "product_display_name", "parent_product_name", "variant_name", "available_qty", "minimum_allowed_price"])
        rows: list[dict[str, object]] = []
        for row in items.itertuples(index=False):
            product_id = str(row.product_id)
            qty = self._to_float(row.qty)
            price = self._to_float(row.unit_selling_price)
            parent_name = ""
            variant_name = ""
            display_name = product_id
            variants = self.variants_repo.all() if self.variants_repo is not None else pd.DataFrame()
            products = self.products_repo.all()
            if not variants.empty:
                vm = variants[(variants["client_id"] == client_id) & (variants["variant_id"] == product_id)]
                if not vm.empty:
                    variant_name = str(vm.iloc[0].get("variant_name", ""))
                    parent_id = str(vm.iloc[0].get("parent_product_id", ""))
                    pm = products[(products["client_id"] == client_id) & (products["product_id"] == parent_id)] if not products.empty else pd.DataFrame()
                    if not pm.empty:
                        parent_name = str(pm.iloc[0].get("product_name", ""))
                    display_name = f"{parent_name} - {variant_name}".strip(" -")
            if not parent_name and not products.empty:
                pm = products[(products["client_id"] == client_id) & (products["product_id"] == product_id)]
                if not pm.empty:
                    parent_name = str(pm.iloc[0].get("product_name", ""))
                    display_name = parent_name
            rows.append({
                "order_item_id": str(row.order_item_id),
                "order_id": str(row.order_id),
                "product_id": product_id,
                "qty": qty,
                "unit_selling_price": price,
                "line_total": qty * price,
                "product_display_name": display_name,
                "parent_product_name": parent_name,
                "variant_name": variant_name,
                "available_qty": self.inv_service.available_qty(client_id, product_id),
                "minimum_allowed_price": self.min_allowed_price(client_id, product_id),
            })
        return pd.DataFrame(rows)

    def record_payment(self, order_id: str, amount: float, payment_method: str, paid_at: str | None = None, note: str = "", reference: str = "") -> dict[str, float]:
        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        order = self.get_order(order_id)
        if not order:
            raise ValueError("Order not found")
        if order.get("order_status") in ["draft", "cancelled"]:
            raise ValueError("Payments can only be recorded after order placement")
        balance = self._to_float(order.get("balance_due", order.get("grand_total", 0)))
        if amount - balance > 1e-9:
            raise ValueError("Overpayment is blocked")
        invoice = self._ensure_invoice_for_order(order)
        self.payments_repo.append({"payment_id": new_uuid(), "client_id": order["client_id"], "timestamp": paid_at or now_iso(), "invoice_id": invoice.get("invoice_id", ""), "order_id": order_id, "amount_paid": str(amount), "method": payment_method, "note": note, "reference": reference, "status": "successful"})
        return self.compute_invoice_balance(order_id)

    def confirm_sale(self, payload: SaleConfirm, customer_snapshot: dict[str, str], user_id: str = "") -> dict[str, str]:
        order_id = self.create_draft_order(payload.client_id, payload.customer_id, note=payload.note, discount=payload.discount, tax=payload.tax)
        for item in payload.items:
            self.add_item_to_draft(order_id, payload.client_id, item)
        self.place_order_from_draft(order_id, {"client_id": payload.client_id, "user_id": user_id})
        result = self.confirm_order(order_id, {"client_id": payload.client_id, "user_id": user_id})
        return result

    def resolve_customer_for_sale(self, client_id: str, customer_input: dict[str, str], matched_customer_id: str = "", user_id: str = "") -> str:
        if not self.customers_repo:
            raise ValueError("Customer repo unavailable")
        if matched_customer_id:
            existing = self.customers_repo.get(matched_customer_id) or {}
            patch = {}
            for field in ["full_name", "phone", "email", "address_line1"]:
                incoming = customer_input.get(field, "").strip()
                if incoming and incoming != str(existing.get(field, "")).strip():
                    patch[field] = incoming
            if patch:
                self.customers_repo.update(matched_customer_id, patch)
            return matched_customer_id
        customer_id = new_uuid()
        fields = {
            "full_name": customer_input.get("full_name", "").strip(),
            "phone": customer_input.get("phone", "").strip(),
            "email": customer_input.get("email", "").strip(),
            "address_line1": customer_input.get("address_line1", "").strip(),
        }
        self.customers_repo.create({"customer_id": customer_id, "client_id": client_id, "created_at": now_iso(), "full_name": fields["full_name"], "phone": fields["phone"], "email": fields["email"], "whatsapp": fields["phone"], "address_line1": fields["address_line1"], "address_line2": "", "area": "", "city": customer_input.get("city", "").strip(), "state": "", "postal_code": "", "country": customer_input.get("country", "").strip(), "preferred_contact_channel": "phone", "marketing_opt_in": "false", "tags": "", "notes": "", "is_active": "true"})
        if self.audit_repo is not None:
            log_event(self.audit_repo, user_id, client_id, "customer_auto_created_from_sale", "customer", customer_id, fields)
        return customer_id
