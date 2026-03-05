from __future__ import annotations

import pandas as pd

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
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

    def min_allowed_price(self, client_id: str, product_name: str) -> float:
        products = self.products_repo.all()
        if products.empty:
            raise ValueError("Product not found")
        matched = products[(products["client_id"] == client_id) & (products["product_name"] == product_name)]
        if matched.empty:
            raise ValueError("Product not found")
        row = matched.iloc[0]
        default_price = float(row.get("default_selling_price", 0) or 0)
        max_discount_pct = float(row.get("max_discount_pct", 10.0) or 10.0)
        if default_price <= 0:
            raise ValueError("Product default selling price must be configured")
        return default_price * (1 - max_discount_pct / 100)

    def validate_item_pricing(self, client_id: str, item: SaleItem) -> None:
        min_price = self.min_allowed_price(client_id, item.product_id)
        if item.unit_selling_price < min_price:
            raise ValueError(f"Price for {item.product_id} cannot be below {min_price:.2f}")

    def confirm_sale(self, payload: SaleConfirm, customer_snapshot: dict[str, str], user_id: str = "") -> dict[str, str]:
        subtotal = sum(i.qty * i.unit_selling_price for i in payload.items)
        grand_total = subtotal - payload.discount + payload.tax
        order_id = new_uuid()
        self.orders_repo.append({"order_id": order_id, "client_id": payload.client_id, "timestamp": now_iso(), "customer_id": payload.customer_id, "status": "confirmed", "subtotal": str(subtotal), "discount": str(payload.discount), "tax": str(payload.tax), "grand_total": str(grand_total), "note": payload.note})

        for item in payload.items:
            self.validate_item_pricing(payload.client_id, item)
            self.items_repo.append({"order_item_id": new_uuid(), "order_id": order_id, "product_id": item.product_id, "prd_description_snapshot": "", "qty": str(item.qty), "unit_selling_price": str(item.unit_selling_price), "total_selling_price": str(item.qty * item.unit_selling_price)})
            self.inv_service.deduct_stock(payload.client_id, item.product_id, item.qty, "sale", order_id, user_id=user_id)

        year = pd.Timestamp.utcnow().year
        invoice_id = new_uuid()
        invoice_no = self.seq_service.next(payload.client_id, "INVOICE", year, "INV")
        self.invoices_repo.append({"invoice_id": invoice_id, "client_id": payload.client_id, "invoice_no": invoice_no, "order_id": order_id, "customer_id": payload.customer_id, "timestamp": now_iso(), "amount_due": str(grand_total), "status": "unpaid"})

        shipment_id = new_uuid()
        shipment_no = self.seq_service.next(payload.client_id, "SHIPMENT", year, "SHP")
        self.shipments_repo.append({"shipment_id": shipment_id, "client_id": payload.client_id, "shipment_no": shipment_no, "order_id": order_id, "customer_id": payload.customer_id, "timestamp": now_iso(), "status": "packed", "ship_to_name_snapshot": customer_snapshot.get("full_name", ""), "ship_to_phone_snapshot": customer_snapshot.get("phone", ""), "ship_to_address_snapshot": customer_snapshot.get("address_line1", ""), "courier": "", "tracking_no": ""})

        self.finance_service.add_entry(payload.client_id, "earning", "Sales", grand_total, "sale", invoice_id, "Auto-posted sale", user_id=user_id)
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
        status = "unpaid"
        if paid >= amount_due:
            status = "paid"
        elif paid > 0:
            status = "partial"
        invoices.loc[idx[0], "status"] = status
        self.invoices_repo.save(invoices)
