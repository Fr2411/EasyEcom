from __future__ import annotations

import pandas as pd

from easy_ecom.core.audit import log_event
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.repos.csv.audit_repo import AuditRepo
from easy_ecom.data.repos.csv.customers_repo import CustomersRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import (
    InvoicesRepo,
    PaymentsRepo,
    SalesOrderItemsRepo,
    SalesOrdersRepo,
    ShipmentsRepo,
)
from easy_ecom.domain.models.sales import SaleConfirm, SaleItem
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService


class SalesService:
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

    def _get_draft_order_index(self, order_id: str, client_id: str | None = None):
        orders = self.orders_repo.all()
        if orders.empty:
            return orders, None
        scoped = orders[orders["order_id"] == order_id]
        if client_id:
            scoped = scoped[scoped["client_id"] == client_id]
        if scoped.empty:
            return orders, None
        idx = scoped.index[0]
        if orders.loc[idx, "status"] != "draft":
            raise ValueError("Only draft orders can be edited")
        return orders, idx

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
                "subtotal": "0",
                "discount": str(max(0.0, discount)),
                "tax": str(max(0.0, tax)),
                "grand_total": str(max(0.0, -discount + tax + delivery_cost)),
                "delivery_cost": str(max(0.0, delivery_cost)),
                "delivery_provider": delivery_provider,
                "note": note,
            }
        )
        return order_id

    def get_or_create_customer_draft(
        self,
        client_id: str,
        customer_id: str,
        force_new: bool = False,
    ) -> str:
        orders = self.orders_repo.all()
        if not force_new and not orders.empty:
            matched = orders[
                (orders["client_id"] == client_id)
                & (orders["customer_id"] == customer_id)
                & (orders["status"] == "draft")
            ].copy()
            if not matched.empty:
                matched["timestamp"] = pd.to_datetime(matched["timestamp"], errors="coerce")
                matched = matched.sort_values("timestamp", ascending=False)
                return str(matched.iloc[0]["order_id"])
        return self.create_draft_order(client_id, customer_id)

    def recalculate_order_totals(self, order_id: str) -> dict[str, float]:
        totals = self.compute_order_totals(order_id)
        orders = self.orders_repo.all()
        if orders.empty:
            return totals
        idx = orders[orders["order_id"] == order_id].index
        if len(idx) == 0:
            return totals
        i = idx[0]
        orders.loc[i, "subtotal"] = str(totals["subtotal"])
        orders.loc[i, "discount"] = str(totals["discount"])
        orders.loc[i, "tax"] = str(totals["tax"])
        orders.loc[i, "delivery_cost"] = str(totals["delivery_cost"])
        orders.loc[i, "grand_total"] = str(totals["grand_total"])
        self.orders_repo.save(orders)
        return totals

    def update_order_pricing(
        self,
        order_id: str,
        client_id: str,
        discount: float,
        tax: float,
        delivery_cost: float,
        delivery_provider: str,
        note: str,
    ) -> dict[str, float]:
        orders, idx = self._get_draft_order_index(order_id, client_id)
        if idx is None:
            raise ValueError("Order not found")
        orders.loc[idx, "discount"] = str(max(0.0, float(discount)))
        orders.loc[idx, "tax"] = str(max(0.0, float(tax)))
        orders.loc[idx, "delivery_cost"] = str(max(0.0, float(delivery_cost)))
        orders.loc[idx, "delivery_provider"] = str(delivery_provider or "").strip()
        orders.loc[idx, "note"] = str(note or "").strip()
        self.orders_repo.save(orders)
        return self.recalculate_order_totals(order_id)

    def update_order_customer_snapshot(
        self, order_id: str, client_id: str, customer_id: str
    ) -> None:
        if self.customers_repo is not None:
            customers = self.customers_repo.all()
            scoped = customers[
                (customers["client_id"] == client_id) & (customers["customer_id"] == customer_id)
            ]
            if scoped.empty:
                raise ValueError("Customer not found for this client")
        orders, idx = self._get_draft_order_index(order_id, client_id)
        if idx is None:
            raise ValueError("Order not found")
        orders.loc[idx, "customer_id"] = customer_id
        self.orders_repo.save(orders)

    def empty_draft_order(self, order_id: str, client_id: str) -> None:
        order = self.get_order(order_id)
        if not order or order.get("client_id") != client_id:
            raise ValueError("Order not found")
        if order.get("status") != "draft":
            raise ValueError("Only draft orders can be emptied")
        items = self.items_repo.all()
        if not items.empty:
            items = items[items["order_id"] != order_id].reset_index(drop=True)
            self.items_repo.save(items)
        self.recalculate_order_totals(order_id)

    def add_item_to_draft(self, order_id: str, client_id: str, item: SaleItem) -> str:
        order = self.get_order(order_id)
        if not order or order.get("client_id") != client_id:
            raise ValueError("Order not found")
        if order.get("status") != "draft":
            raise ValueError("Only draft orders can be edited")
        self.validate_item_pricing(client_id, item)
        items = self.items_repo.all()
        if items.empty:
            items = pd.DataFrame(
                columns=[
                    "order_item_id",
                    "order_id",
                    "product_id",
                    "prd_description_snapshot",
                    "qty",
                    "unit_selling_price",
                    "total_selling_price",
                ]
            )
        scoped = items[(items["order_id"] == order_id) & (items["product_id"] == item.product_id)]
        if not scoped.empty:
            idx = scoped.index[0]
            new_qty = self._to_float(items.loc[idx, "qty"]) + float(item.qty)
            items.loc[idx, "qty"] = str(new_qty)
            items.loc[idx, "unit_selling_price"] = str(item.unit_selling_price)
            items.loc[idx, "total_selling_price"] = str(new_qty * item.unit_selling_price)
            saved_order_item_id = str(items.loc[idx, "order_item_id"])
            self.items_repo.save(items)
        else:
            saved_order_item_id = new_uuid()
            self.items_repo.append(
                {
                    "order_item_id": saved_order_item_id,
                    "order_id": order_id,
                    "product_id": item.product_id,
                    "prd_description_snapshot": "",
                    "qty": str(item.qty),
                    "unit_selling_price": str(item.unit_selling_price),
                    "total_selling_price": str(item.qty * item.unit_selling_price),
                }
            )
        self.recalculate_order_totals(order_id)
        return saved_order_item_id

    def list_draft_orders(self, client_id: str) -> pd.DataFrame:
        orders = self.orders_repo.all()
        if orders.empty:
            return pd.DataFrame(
                columns=[
                    "order_id",
                    "client_id",
                    "timestamp",
                    "customer_id",
                    "status",
                    "subtotal",
                    "discount",
                    "tax",
                    "grand_total",
                    "delivery_cost",
                    "delivery_provider",
                    "note",
                    "item_count",
                ]
            )
        scoped = orders[(orders["client_id"] == client_id) & (orders["status"] == "draft")].copy()
        if scoped.empty:
            scoped["item_count"] = []
            return scoped
        items = self.items_repo.all()
        counts = (
            items.groupby("order_id", as_index=False).size().rename(columns={"size": "item_count"})
            if not items.empty
            else pd.DataFrame(columns=["order_id", "item_count"])
        )
        scoped = scoped.merge(counts, on="order_id", how="left")
        scoped["item_count"] = scoped["item_count"].fillna(0).astype(int)
        return scoped

    def get_order(self, order_id: str) -> dict[str, str] | None:
        orders = self.orders_repo.all()
        row = orders[orders["order_id"] == order_id] if not orders.empty else pd.DataFrame()
        return None if row.empty else row.iloc[0].to_dict()

    def get_order_items(self, order_id: str) -> pd.DataFrame:
        items = self.items_repo.all()
        if items.empty:
            return pd.DataFrame(
                columns=[
                    "order_item_id",
                    "order_id",
                    "product_id",
                    "prd_description_snapshot",
                    "qty",
                    "unit_selling_price",
                    "total_selling_price",
                ]
            )
        return items[items["order_id"] == order_id].copy()

    def compute_order_totals(self, order_id: str) -> dict[str, float]:
        order = self.get_order(order_id) or {}
        discount = max(0.0, self._to_float(order.get("discount", 0)))
        tax = max(0.0, self._to_float(order.get("tax", 0)))
        delivery_cost = max(0.0, self._to_float(order.get("delivery_cost", 0)))
        items = self.get_order_items(order_id)
        if items.empty:
            grand_total = max(0.0, 0.0 - discount + tax + delivery_cost)
            return {
                "item_count": 0,
                "subtotal": 0.0,
                "discount": discount,
                "tax": tax,
                "delivery_cost": delivery_cost,
                "grand_total": grand_total,
            }
        items["qty"] = items["qty"].astype(float)
        items["unit_selling_price"] = items["unit_selling_price"].astype(float)
        subtotal = float((items["qty"] * items["unit_selling_price"]).sum())
        grand_total = max(0.0, subtotal - discount + tax + delivery_cost)
        return {
            "item_count": int(items["qty"].sum()),
            "subtotal": subtotal,
            "discount": discount,
            "tax": tax,
            "delivery_cost": delivery_cost,
            "grand_total": grand_total,
        }

    def cancel_draft_order(self, order_id: str) -> bool:
        orders = self.orders_repo.all()
        idx = orders[orders["order_id"] == order_id].index if not orders.empty else []
        if len(idx) == 0 or orders.loc[idx[0], "status"] != "draft":
            return False
        orders.loc[idx[0], "status"] = "cancelled"
        self.orders_repo.save(orders)
        return True

    def update_delivery(
        self, order_id: str, client_id: str, delivery_cost: float, delivery_provider: str = ""
    ) -> None:
        order = self.get_order(order_id)
        if not order:
            raise ValueError("Order not found")
        self.update_order_pricing(
            order_id,
            client_id,
            discount=self._to_float(order.get("discount", 0)),
            tax=self._to_float(order.get("tax", 0)),
            delivery_cost=delivery_cost,
            delivery_provider=delivery_provider,
            note=str(order.get("note", "")),
        )

    def update_draft_item(
        self, order_item_id: str, qty: float, unit_price: float, client_id: str
    ) -> None:
        items = self.items_repo.all()
        idx = items[items["order_item_id"] == order_item_id].index
        if len(idx) == 0:
            raise ValueError("Order item not found")
        i = idx[0]
        order = self.get_order(str(items.loc[i, "order_id"]))
        if not order or order.get("client_id") != client_id or order.get("status") != "draft":
            raise ValueError("Only draft orders can be edited")
        product_id = str(items.loc[i, "product_id"])
        self.validate_item_pricing(
            client_id, SaleItem(product_id=product_id, qty=qty, unit_selling_price=unit_price)
        )
        items.loc[i, "qty"] = str(qty)
        items.loc[i, "unit_selling_price"] = str(unit_price)
        items.loc[i, "total_selling_price"] = str(qty * unit_price)
        self.items_repo.save(items)
        self.recalculate_order_totals(str(items.loc[i, "order_id"]))

    def remove_draft_item(self, order_item_id: str, client_id: str) -> None:
        items = self.items_repo.all()
        idx = items[items["order_item_id"] == order_item_id].index
        if len(idx) == 0:
            return
        i = idx[0]
        order = self.get_order(str(items.loc[i, "order_id"]))
        if not order or order.get("client_id") != client_id or order.get("status") != "draft":
            raise ValueError("Only draft order items can be removed")
        order_id = str(items.loc[i, "order_id"])
        self.items_repo.save(items.drop(index=i).reset_index(drop=True))
        self.recalculate_order_totals(order_id)

    def resolve_order_items(self, client_id: str, order_id: str) -> pd.DataFrame:
        items = self.get_order_items(order_id)
        if items.empty:
            return pd.DataFrame(
                columns=[
                    "order_item_id",
                    "order_id",
                    "product_id",
                    "qty",
                    "unit_selling_price",
                    "line_total",
                    "product_display_name",
                    "parent_product_name",
                    "variant_name",
                    "available_qty",
                    "minimum_allowed_price",
                ]
            )
        items = items.copy()
        products = self.products_repo.all()
        scoped_products = (
            products[products["client_id"] == client_id].copy()
            if not products.empty
            else pd.DataFrame(
                columns=["product_id", "product_name", "default_selling_price", "max_discount_pct"]
            )
        )
        variants = self.variants_repo.all() if self.variants_repo is not None else pd.DataFrame()
        scoped_variants = (
            variants[variants["client_id"] == client_id].copy()
            if not variants.empty
            else pd.DataFrame(
                columns=[
                    "variant_id",
                    "parent_product_id",
                    "variant_name",
                    "default_selling_price",
                    "max_discount_pct",
                ]
            )
        )

        parent_lookup = (
            scoped_products.set_index("product_id").to_dict("index")
            if not scoped_products.empty
            else {}
        )
        variant_lookup = (
            scoped_variants.set_index("variant_id").to_dict("index")
            if not scoped_variants.empty
            else {}
        )

        rows: list[dict[str, object]] = []
        for row in items.itertuples(index=False):
            product_id = str(row.product_id)
            variant = variant_lookup.get(product_id)
            parent_name = ""
            variant_name = ""
            display_name = product_id
            if variant:
                parent = parent_lookup.get(str(variant.get("parent_product_id", "")), {})
                parent_name = str(parent.get("product_name", ""))
                variant_name = str(variant.get("variant_name", ""))
                display_name = (
                    f"{parent_name} - {variant_name}" if parent_name else variant_name or product_id
                )
            else:
                parent = parent_lookup.get(product_id, {})
                parent_name = str(parent.get("product_name", ""))
                display_name = parent_name or product_id
            qty = self._to_float(row.qty)
            unit_price = self._to_float(row.unit_selling_price)
            rows.append(
                {
                    "order_item_id": str(row.order_item_id),
                    "order_id": str(row.order_id),
                    "product_id": product_id,
                    "qty": qty,
                    "unit_selling_price": unit_price,
                    "line_total": qty * unit_price,
                    "product_display_name": display_name,
                    "parent_product_name": parent_name,
                    "variant_name": variant_name,
                    "available_qty": self.inv_service.available_qty(client_id, product_id),
                    "minimum_allowed_price": self.min_allowed_price(client_id, product_id),
                }
            )
        return pd.DataFrame(rows)

    def confirm_order(self, order_id: str, user_ctx: dict[str, str]) -> dict[str, str]:
        order = self.get_order(order_id)
        if not order:
            raise ValueError("Order not found")
        if order.get("status") != "draft":
            raise ValueError(f"Order already {order.get('status')}")
        client_id = str(order.get("client_id", ""))
        if user_ctx.get("client_id") and user_ctx["client_id"] != client_id:
            raise ValueError("Order does not belong to active client")

        items = self.get_order_items(order_id)
        if items.empty:
            raise ValueError("Draft order has no items")
        totals = self.compute_order_totals(order_id)
        for row in items.itertuples(index=False):
            item = SaleItem(
                product_id=str(row.product_id),
                qty=float(row.qty),
                unit_selling_price=float(row.unit_selling_price),
            )
            self.validate_item_pricing(client_id, item)
            self.inv_service.allocate_fifo(client_id, item.product_id, item.qty)
        for row in items.itertuples(index=False):
            self.inv_service.deduct_stock(
                client_id,
                str(row.product_id),
                float(row.qty),
                "sale",
                order_id,
                user_id=user_ctx.get("user_id", ""),
            )

        year = pd.Timestamp.utcnow().year
        invoice_id = new_uuid()
        invoice_no = self.seq_service.next(client_id, "INVOICE", year, "INV")
        shipment_id = new_uuid()
        shipment_no = self.seq_service.next(client_id, "SHIPMENT", year, "SHP")

        self.invoices_repo.append(
            {
                "invoice_id": invoice_id,
                "client_id": client_id,
                "invoice_no": invoice_no,
                "order_id": order_id,
                "customer_id": order.get("customer_id", ""),
                "timestamp": now_iso(),
                "amount_due": str(totals["grand_total"]),
                "status": "unpaid",
            }
        )
        customer = (
            self.customers_repo.get(str(order.get("customer_id", "")))
            if self.customers_repo
            else {}
        )
        customer = customer or {}
        self.shipments_repo.append(
            {
                "shipment_id": shipment_id,
                "client_id": client_id,
                "shipment_no": shipment_no,
                "order_id": order_id,
                "customer_id": order.get("customer_id", ""),
                "timestamp": now_iso(),
                "status": "packed",
                "ship_to_name_snapshot": customer.get("full_name", ""),
                "ship_to_phone_snapshot": customer.get("phone", ""),
                "ship_to_address_snapshot": customer.get("address_line1", ""),
                "courier": "",
                "tracking_no": "",
            }
        )
        self.finance_service.add_entry(
            client_id,
            "earning",
            "Sales",
            totals["grand_total"],
            "sale",
            invoice_id,
            "Auto-posted sale",
            user_id=user_ctx.get("user_id", ""),
        )

        delivery_cost = totals["delivery_cost"]
        if delivery_cost > 0:
            self.finance_service.add_entry(
                client_id,
                "expense",
                "Delivery",
                delivery_cost,
                "delivery",
                order_id,
                "Auto-posted delivery",
                user_id=user_ctx.get("user_id", ""),
            )

        orders = self.orders_repo.all()
        idx = orders[orders["order_id"] == order_id].index
        i = idx[0]
        orders.loc[i, "status"] = "confirmed"
        orders.loc[i, "subtotal"] = str(totals["subtotal"])
        orders.loc[i, "discount"] = str(totals["discount"])
        orders.loc[i, "tax"] = str(totals["tax"])
        orders.loc[i, "delivery_cost"] = str(totals["delivery_cost"])
        orders.loc[i, "grand_total"] = str(totals["grand_total"])
        self.orders_repo.save(orders)
        return {
            "invoice_id": invoice_id,
            "shipment_id": shipment_id,
            "invoice_no": invoice_no,
            "shipment_no": shipment_no,
        }

    def min_allowed_price(self, client_id: str, product_id: str) -> float:
        if self.variants_repo is not None:
            variants = self.variants_repo.all()
            if not variants.empty:
                vm = variants[
                    (variants["client_id"] == client_id) & (variants["variant_id"] == product_id)
                ]
                if not vm.empty:
                    row = vm.iloc[0]
                    base = float(row.get("default_selling_price", 0) or 0)
                    disc = float(row.get("max_discount_pct", 10) or 10)
                    return base * (1 - disc / 100)
        products = self.products_repo.all()
        matched = (
            products[(products["client_id"] == client_id) & (products["product_id"] == product_id)]
            if not products.empty
            else pd.DataFrame()
        )
        if matched.empty:
            raise ValueError("Product not found")
        row = matched.iloc[0]
        default_price = float(row.get("default_selling_price", 0) or 0)
        max_discount_pct = float(row.get("max_discount_pct", 10.0) or 10.0)
        if default_price <= 0:
            raise ValueError("Product default selling price must be configured")
        return default_price * (1 - max_discount_pct / 100)

    def validate_item_pricing(self, client_id: str, item: SaleItem) -> None:
        if item.unit_selling_price < self.min_allowed_price(client_id, item.product_id):
            raise ValueError(f"Price for {item.product_id} is below minimum")

    def resolve_customer_for_sale(
        self,
        client_id: str,
        customer_input: dict[str, str],
        matched_customer_id: str = "",
        user_id: str = "",
    ) -> str:
        if self.customers_repo is None:
            return customer_input.get("customer_id", "")
        full_name = customer_input.get("full_name", "").strip()
        if not full_name:
            raise ValueError("Customer name is required")
        fields = {
            "full_name": full_name,
            "phone": customer_input.get("phone", "").strip(),
            "email": customer_input.get("email", "").strip(),
            "address_line1": customer_input.get("address_line1", "").strip(),
        }
        if matched_customer_id:
            customers = self.customers_repo.all()
            scoped = customers[
                (customers["client_id"] == client_id)
                & (customers["customer_id"] == matched_customer_id)
            ]
            if scoped.empty:
                raise ValueError("Selected customer does not belong to current client")
            patch = {k: v for k, v in fields.items() if str(scoped.iloc[0].get(k, "")) != v}
            if patch:
                self.customers_repo.update(matched_customer_id, patch)
                if self.audit_repo is not None:
                    log_event(
                        self.audit_repo,
                        user_id,
                        client_id,
                        "customer_auto_updated_from_sale",
                        "customer",
                        matched_customer_id,
                        {"patch": patch},
                    )
            return matched_customer_id
        customer_id = new_uuid()
        self.customers_repo.create(
            {
                "customer_id": customer_id,
                "client_id": client_id,
                "created_at": now_iso(),
                "full_name": fields["full_name"],
                "phone": fields["phone"],
                "email": fields["email"],
                "whatsapp": fields["phone"],
                "address_line1": fields["address_line1"],
                "address_line2": "",
                "area": "",
                "city": customer_input.get("city", "").strip(),
                "state": "",
                "postal_code": "",
                "country": customer_input.get("country", "").strip(),
                "preferred_contact_channel": "phone",
                "marketing_opt_in": "false",
                "tags": "",
                "notes": "",
                "is_active": "true",
            }
        )
        if self.audit_repo is not None:
            log_event(
                self.audit_repo,
                user_id,
                client_id,
                "customer_auto_created_from_sale",
                "customer",
                customer_id,
                fields,
            )
        return customer_id

    def confirm_sale(
        self, payload: SaleConfirm, customer_snapshot: dict[str, str], user_id: str = ""
    ) -> dict[str, str]:
        subtotal = sum(i.qty * i.unit_selling_price for i in payload.items)
        discount = max(0.0, float(payload.discount))
        tax = max(0.0, float(payload.tax))
        grand_total = max(0.0, subtotal - discount + tax)
        order_id = new_uuid()
        self.orders_repo.append(
            {
                "order_id": order_id,
                "client_id": payload.client_id,
                "timestamp": now_iso(),
                "customer_id": payload.customer_id,
                "status": "confirmed",
                "subtotal": str(subtotal),
                "discount": str(discount),
                "tax": str(tax),
                "grand_total": str(grand_total),
                "delivery_cost": "0",
                "delivery_provider": "",
                "note": payload.note,
            }
        )
        for item in payload.items:
            self.validate_item_pricing(payload.client_id, item)
            self.items_repo.append(
                {
                    "order_item_id": new_uuid(),
                    "order_id": order_id,
                    "product_id": item.product_id,
                    "prd_description_snapshot": "",
                    "qty": str(item.qty),
                    "unit_selling_price": str(item.unit_selling_price),
                    "total_selling_price": str(item.qty * item.unit_selling_price),
                }
            )
            self.inv_service.deduct_stock(
                payload.client_id, item.product_id, item.qty, "sale", order_id, user_id=user_id
            )
        year = pd.Timestamp.utcnow().year
        invoice_id = new_uuid()
        invoice_no = self.seq_service.next(payload.client_id, "INVOICE", year, "INV")
        self.invoices_repo.append(
            {
                "invoice_id": invoice_id,
                "client_id": payload.client_id,
                "invoice_no": invoice_no,
                "order_id": order_id,
                "customer_id": payload.customer_id,
                "timestamp": now_iso(),
                "amount_due": str(grand_total),
                "status": "unpaid",
            }
        )
        shipment_id = new_uuid()
        shipment_no = self.seq_service.next(payload.client_id, "SHIPMENT", year, "SHP")
        self.shipments_repo.append(
            {
                "shipment_id": shipment_id,
                "client_id": payload.client_id,
                "shipment_no": shipment_no,
                "order_id": order_id,
                "customer_id": payload.customer_id,
                "timestamp": now_iso(),
                "status": "packed",
                "ship_to_name_snapshot": customer_snapshot.get("full_name", ""),
                "ship_to_phone_snapshot": customer_snapshot.get("phone", ""),
                "ship_to_address_snapshot": customer_snapshot.get("address_line1", ""),
                "courier": "",
                "tracking_no": "",
            }
        )
        self.finance_service.add_entry(
            payload.client_id,
            "earning",
            "Sales",
            grand_total,
            "sale",
            invoice_id,
            "Auto-posted sale",
            user_id=user_id,
        )
        return {
            "order_id": order_id,
            "invoice_id": invoice_id,
            "shipment_id": shipment_id,
            "invoice_no": invoice_no,
            "shipment_no": shipment_no,
        }

    def record_payment(
        self, client_id: str, invoice_id: str, amount_paid: float, method: str, note: str = ""
    ) -> None:
        self.payments_repo.append(
            {
                "payment_id": new_uuid(),
                "client_id": client_id,
                "timestamp": now_iso(),
                "invoice_id": invoice_id,
                "amount_paid": str(amount_paid),
                "method": method,
                "note": note,
            }
        )
        invoices = self.invoices_repo.all()
        if invoices.empty:
            return
        payments = self.payments_repo.all()
        paid = payments[payments["invoice_id"] == invoice_id]["amount_paid"].astype(float).sum()
        idx = invoices[invoices["invoice_id"] == invoice_id].index
        if len(idx) == 0:
            return
        amount_due = float(invoices.loc[idx[0], "amount_due"])
        invoices.loc[idx[0], "status"] = (
            "paid" if paid >= amount_due else ("partial" if paid > 0 else "unpaid")
        )
        self.invoices_repo.save(invoices)
