from __future__ import annotations

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

    def list_draft_orders(self, client_id: str) -> pd.DataFrame:
        orders = self.orders_repo.all()
        if orders.empty:
            return pd.DataFrame(columns=["order_id", "client_id", "timestamp", "customer_id", "status", "subtotal", "discount", "tax", "grand_total", "delivery_cost", "delivery_provider", "note", "item_count"])
        scoped = orders[(orders["client_id"] == client_id) & (orders["status"] == "draft")].copy()
        if scoped.empty:
            scoped["item_count"] = []
            return scoped
        items = self.items_repo.all()
        counts = items.groupby("order_id", as_index=False).size().rename(columns={"size": "item_count"}) if not items.empty else pd.DataFrame(columns=["order_id", "item_count"])
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
            return pd.DataFrame(columns=["order_item_id", "order_id", "product_id", "prd_description_snapshot", "qty", "unit_selling_price", "total_selling_price"])
        return items[items["order_id"] == order_id].copy()

    def compute_order_totals(self, order_id: str) -> dict[str, float]:
        items = self.get_order_items(order_id)
        if items.empty:
            return {"item_count": 0, "subtotal": 0.0, "grand_total": 0.0}
        items["qty"] = items["qty"].astype(float)
        items["unit_selling_price"] = items["unit_selling_price"].astype(float)
        subtotal = float((items["qty"] * items["unit_selling_price"]).sum())
        return {"item_count": int(len(items)), "subtotal": subtotal, "grand_total": subtotal}

    def cancel_draft_order(self, order_id: str) -> bool:
        orders = self.orders_repo.all()
        idx = orders[orders["order_id"] == order_id].index if not orders.empty else []
        if len(idx) == 0 or orders.loc[idx[0], "status"] != "draft":
            return False
        orders.loc[idx[0], "status"] = "cancelled"
        self.orders_repo.save(orders)
        return True

    def update_delivery(self, order_id: str, client_id: str, delivery_cost: float, delivery_provider: str = "") -> None:
        orders = self.orders_repo.all()
        idx = orders[(orders["order_id"] == order_id) & (orders["client_id"] == client_id)].index
        if len(idx) == 0:
            raise ValueError("Order not found")
        i = idx[0]
        if orders.loc[i, "status"] != "draft":
            raise ValueError("Only draft orders can be edited")
        orders.loc[i, "delivery_cost"] = str(max(0.0, float(delivery_cost)))
        orders.loc[i, "delivery_provider"] = delivery_provider
        self.orders_repo.save(orders)

    def update_draft_item(self, order_item_id: str, qty: float, unit_price: float, client_id: str) -> None:
        items = self.items_repo.all()
        idx = items[items["order_item_id"] == order_item_id].index
        if len(idx) == 0:
            raise ValueError("Order item not found")
        i = idx[0]
        order = self.get_order(str(items.loc[i, "order_id"]))
        if not order or order.get("client_id") != client_id or order.get("status") != "draft":
            raise ValueError("Only draft orders can be edited")
        product_id = str(items.loc[i, "product_id"])
        self.validate_item_pricing(client_id, SaleItem(product_id=product_id, qty=qty, unit_selling_price=unit_price))
        items.loc[i, "qty"] = str(qty)
        items.loc[i, "unit_selling_price"] = str(unit_price)
        items.loc[i, "total_selling_price"] = str(qty * unit_price)
        self.items_repo.save(items)

    def remove_draft_item(self, order_item_id: str, client_id: str) -> None:
        items = self.items_repo.all()
        idx = items[items["order_item_id"] == order_item_id].index
        if len(idx) == 0:
            return
        i = idx[0]
        order = self.get_order(str(items.loc[i, "order_id"]))
        if not order or order.get("client_id") != client_id or order.get("status") != "draft":
            raise ValueError("Only draft order items can be removed")
        self.items_repo.save(items.drop(index=i).reset_index(drop=True))

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
        subtotal = 0.0
        for row in items.itertuples(index=False):
            item = SaleItem(product_id=str(row.product_id), qty=float(row.qty), unit_selling_price=float(row.unit_selling_price))
            self.validate_item_pricing(client_id, item)
            self.inv_service.allocate_fifo(client_id, item.product_id, item.qty)
            subtotal += item.qty * item.unit_selling_price
        for row in items.itertuples(index=False):
            self.inv_service.deduct_stock(client_id, str(row.product_id), float(row.qty), "sale", order_id, user_id=user_ctx.get("user_id", ""))

        year = pd.Timestamp.utcnow().year
        invoice_id = new_uuid()
        invoice_no = self.seq_service.next(client_id, "INVOICE", year, "INV")
        shipment_id = new_uuid()
        shipment_no = self.seq_service.next(client_id, "SHIPMENT", year, "SHP")

        self.invoices_repo.append({"invoice_id": invoice_id, "client_id": client_id, "invoice_no": invoice_no, "order_id": order_id, "customer_id": order.get("customer_id", ""), "timestamp": now_iso(), "amount_due": str(subtotal), "status": "unpaid"})
        customer = self.customers_repo.get(str(order.get("customer_id", ""))) if self.customers_repo else {}
        customer = customer or {}
        self.shipments_repo.append({"shipment_id": shipment_id, "client_id": client_id, "shipment_no": shipment_no, "order_id": order_id, "customer_id": order.get("customer_id", ""), "timestamp": now_iso(), "status": "packed", "ship_to_name_snapshot": customer.get("full_name", ""), "ship_to_phone_snapshot": customer.get("phone", ""), "ship_to_address_snapshot": customer.get("address_line1", ""), "courier": "", "tracking_no": ""})
        self.finance_service.add_entry(client_id, "earning", "Sales", subtotal, "sale", invoice_id, "Auto-posted sale", user_id=user_ctx.get("user_id", ""))

        delivery_cost = float(order.get("delivery_cost", 0) or 0)
        if delivery_cost > 0:
            self.finance_service.add_entry(client_id, "expense", "Delivery", delivery_cost, "delivery", order_id, "Auto-posted delivery", user_id=user_ctx.get("user_id", ""))

        orders = self.orders_repo.all()
        idx = orders[orders["order_id"] == order_id].index
        i = idx[0]
        orders.loc[i, "status"] = "confirmed"
        orders.loc[i, "subtotal"] = str(subtotal)
        orders.loc[i, "discount"] = "0"
        orders.loc[i, "tax"] = "0"
        orders.loc[i, "grand_total"] = str(subtotal)
        self.orders_repo.save(orders)
        return {"invoice_id": invoice_id, "shipment_id": shipment_id, "invoice_no": invoice_no, "shipment_no": shipment_no}

    def min_allowed_price(self, client_id: str, product_id: str) -> float:
        if self.variants_repo is not None:
            variants = self.variants_repo.all()
            if not variants.empty:
                vm = variants[(variants["client_id"] == client_id) & (variants["variant_id"] == product_id)]
                if not vm.empty:
                    row = vm.iloc[0]
                    base = float(row.get("default_selling_price", 0) or 0)
                    disc = float(row.get("max_discount_pct", 10) or 10)
                    return base * (1 - disc / 100)
        products = self.products_repo.all()
        matched = products[(products["client_id"] == client_id) & (products["product_id"] == product_id)] if not products.empty else pd.DataFrame()
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

    def resolve_customer_for_sale(self, client_id: str, customer_input: dict[str, str], matched_customer_id: str = "", user_id: str = "") -> str:
        if self.customers_repo is None:
            return customer_input.get("customer_id", "")
        full_name = customer_input.get("full_name", "").strip()
        if not full_name:
            raise ValueError("Customer name is required")
        fields = {"full_name": full_name, "phone": customer_input.get("phone", "").strip(), "email": customer_input.get("email", "").strip(), "address_line1": customer_input.get("address_line1", "").strip()}
        if matched_customer_id:
            customers = self.customers_repo.all()
            scoped = customers[(customers["client_id"] == client_id) & (customers["customer_id"] == matched_customer_id)]
            if scoped.empty:
                raise ValueError("Selected customer does not belong to current client")
            patch = {k: v for k, v in fields.items() if str(scoped.iloc[0].get(k, "")) != v}
            if patch:
                self.customers_repo.update(matched_customer_id, patch)
                if self.audit_repo is not None:
                    log_event(self.audit_repo, user_id, client_id, "customer_auto_updated_from_sale", "customer", matched_customer_id, {"patch": patch})
            return matched_customer_id
        customer_id = new_uuid()
        self.customers_repo.create({"customer_id": customer_id, "client_id": client_id, "created_at": now_iso(), "full_name": fields["full_name"], "phone": fields["phone"], "email": fields["email"], "whatsapp": fields["phone"], "address_line1": fields["address_line1"], "address_line2": "", "area": "", "city": customer_input.get("city", "").strip(), "state": "", "postal_code": "", "country": customer_input.get("country", "").strip(), "preferred_contact_channel": "phone", "marketing_opt_in": "false", "tags": "", "notes": "", "is_active": "true"})
        if self.audit_repo is not None:
            log_event(self.audit_repo, user_id, client_id, "customer_auto_created_from_sale", "customer", customer_id, fields)
        return customer_id

    def confirm_sale(self, payload: SaleConfirm, customer_snapshot: dict[str, str], user_id: str = "") -> dict[str, str]:
        subtotal = sum(i.qty * i.unit_selling_price for i in payload.items)
        order_id = new_uuid()
        self.orders_repo.append({"order_id": order_id, "client_id": payload.client_id, "timestamp": now_iso(), "customer_id": payload.customer_id, "status": "confirmed", "subtotal": str(subtotal), "discount": str(payload.discount), "tax": str(payload.tax), "grand_total": str(subtotal), "delivery_cost": "0", "delivery_provider": "", "note": payload.note})
        for item in payload.items:
            self.validate_item_pricing(payload.client_id, item)
            self.items_repo.append({"order_item_id": new_uuid(), "order_id": order_id, "product_id": item.product_id, "prd_description_snapshot": "", "qty": str(item.qty), "unit_selling_price": str(item.unit_selling_price), "total_selling_price": str(item.qty * item.unit_selling_price)})
            self.inv_service.deduct_stock(payload.client_id, item.product_id, item.qty, "sale", order_id, user_id=user_id)
        year = pd.Timestamp.utcnow().year
        invoice_id = new_uuid()
        invoice_no = self.seq_service.next(payload.client_id, "INVOICE", year, "INV")
        self.invoices_repo.append({"invoice_id": invoice_id, "client_id": payload.client_id, "invoice_no": invoice_no, "order_id": order_id, "customer_id": payload.customer_id, "timestamp": now_iso(), "amount_due": str(subtotal), "status": "unpaid"})
        shipment_id = new_uuid()
        shipment_no = self.seq_service.next(payload.client_id, "SHIPMENT", year, "SHP")
        self.shipments_repo.append({"shipment_id": shipment_id, "client_id": payload.client_id, "shipment_no": shipment_no, "order_id": order_id, "customer_id": payload.customer_id, "timestamp": now_iso(), "status": "packed", "ship_to_name_snapshot": customer_snapshot.get("full_name", ""), "ship_to_phone_snapshot": customer_snapshot.get("phone", ""), "ship_to_address_snapshot": customer_snapshot.get("address_line1", ""), "courier": "", "tracking_no": ""})
        self.finance_service.add_entry(payload.client_id, "earning", "Sales", subtotal, "sale", invoice_id, "Auto-posted sale", user_id=user_id)
        return {"order_id": order_id, "invoice_id": invoice_id, "shipment_id": shipment_id, "invoice_no": invoice_no, "shipment_no": shipment_no}

    def record_payment(self, client_id: str, invoice_id: str, amount_paid: float, method: str, note: str = "") -> None:
        self.payments_repo.append({"payment_id": new_uuid(), "client_id": client_id, "timestamp": now_iso(), "invoice_id": invoice_id, "amount_paid": str(amount_paid), "method": method, "note": note})
        invoices = self.invoices_repo.all()
        if invoices.empty:
            return
        payments = self.payments_repo.all()
        paid = payments[payments["invoice_id"] == invoice_id]["amount_paid"].astype(float).sum()
        idx = invoices[invoices["invoice_id"] == invoice_id].index
        if len(idx) == 0:
            return
        amount_due = float(invoices.loc[idx[0], "amount_due"])
        invoices.loc[idx[0], "status"] = "paid" if paid >= amount_due else ("partial" if paid > 0 else "unpaid")
        self.invoices_repo.save(invoices)
