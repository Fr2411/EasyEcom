import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.app.ui.formatters import format_money
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.data.repos.csv.audit_repo import AuditRepo
from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.customers_repo import CustomersRepo
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, PaymentsRepo, SalesOrderItemsRepo, SalesOrdersRepo, ShipmentsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.domain.models.sales import SaleConfirm, SaleItem
from easy_ecom.domain.services.client_service import ClientService
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService
from easy_ecom.domain.services.sales_service import SalesService

require_login()
roles = st.session_state["user"]["roles"].split(",")
if not can_access_page(roles, "Sales"):
    st.error("Access denied")
    st.stop()

store = CsvStore(settings.data_dir)
seq = SequenceService(SequencesRepo(store))
inv = InventoryService(InventoryTxnRepo(store), seq)
fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
svc = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), inv, seq, fin, ProductsRepo(store), CustomersRepo(store), AuditRepo(store))
product_svc = ProductService(ProductsRepo(store), None)
client_svc = ClientService(ClientsRepo(store))

user = st.session_state["user"]
client_id = user["client_id"]
currency_code, currency_symbol = client_svc.get_currency(client_id)

for key, default in [
    ("selected_cart_order_id", ""),
    ("selected_order_id", ""),
    ("sales_selected_customer_id", ""),
    ("sales_selected_customer_label", ""),
    ("sales_last_cart_result", None),
    ("sales_last_payment_result", None),
    ("sales_last_fulfillment_result", None),
    ("sales_last_return_result", None),
    ("sales_force_new_cart", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

st.title("Sales Order Workspace")

st.subheader("Sell / Draft Builder")
products = product_svc.list_by_client(client_id)
product_name = st.selectbox("Product", sorted(products["product_name"].tolist()) if not products.empty else [], index=None)
selected = product_svc.get_by_name(client_id, product_name) if product_name else None
qty = st.number_input("Qty", min_value=0.01, value=1.0)
price = st.number_input("Unit Price", min_value=0.01, value=float((selected or {}).get("default_selling_price", 0.01) or 0.01))
customer_id = st.text_input("Customer ID")
c1, c2, c3 = st.columns(3)
if c1.button("Add to Cart"):
    try:
        draft = svc.get_or_create_customer_draft(client_id, customer_id, force_new=st.session_state["sales_force_new_cart"])
        svc.add_item_to_draft(draft, client_id, SaleItem(product_id=selected["product_id"], qty=qty, unit_selling_price=price))
        st.session_state["selected_order_id"] = draft
        st.success(f"Added to draft {draft}")
    except Exception as exc:
        st.error(str(exc))
if c2.button("Start New Cart"):
    st.session_state["sales_force_new_cart"] = True
if c3.button("Go to Cart"):
    st.info("Use Draft / Order Workspace below.")
with st.expander("Quick Confirm (Legacy)"):
    if st.button("Confirm Sale"):
        try:
            payload = SaleConfirm(client_id=client_id, customer_id=customer_id, items=[SaleItem(product_id=selected["product_id"], qty=qty, unit_selling_price=price)])
            result = svc.confirm_sale(payload, {}, user_id=user["user_id"])
            st.success(f"Confirmed {result['order_id']}")
        except Exception as exc:
            st.error(str(exc))

st.subheader("Draft / Order Workspace")
orders = svc.orders_repo.all()
client_orders = orders[orders["client_id"] == client_id] if not orders.empty else orders
order_id = st.selectbox("Order", client_orders["order_id"].tolist() if not client_orders.empty else [], index=None)
if order_id:
    st.session_state["selected_order_id"] = order_id
order_id = st.session_state.get("selected_order_id")

if order_id:
    order = svc.get_order(order_id)
    if order:
        totals = svc.compute_order_totals(order_id)
        financials = svc.compute_invoice_balance(order_id)
        sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
        sc1.metric("Order", order.get("order_status", "draft"))
        sc2.metric("Payment", order.get("payment_status", "unpaid"))
        sc3.metric("Fulfillment", order.get("fulfillment_status", "unfulfilled"))
        sc4.metric("Return", order.get("return_status", "none"))
        sc5.metric("Grand", format_money(totals["grand_total"], currency_code, currency_symbol))
        sc6.metric("Balance", format_money(financials["balance_due"], currency_code, currency_symbol))

        st.markdown("### Customer block")
        st.write(f"Customer ID: {order.get('customer_id', '')}")

        st.markdown("### Line items block")
        lines = svc.resolve_order_items(client_id, order_id)
        st.dataframe(lines[["product_display_name", "available_qty", "qty", "unit_selling_price", "line_total", "minimum_allowed_price"]], use_container_width=True)

        st.markdown("### Pricing block")
        discount = st.number_input("Discount", min_value=0.0, value=float(order.get("discount", 0) or 0))
        tax = st.number_input("Tax", min_value=0.0, value=float(order.get("tax", 0) or 0))
        delivery_cost = st.number_input("Delivery Cost", min_value=0.0, value=float(order.get("delivery_cost", 0) or 0))
        delivery_provider = st.text_input("Delivery Provider", value=order.get("delivery_provider", ""))
        note = st.text_area("Note", value=order.get("note", ""))
        if st.button("Save Pricing"):
            try:
                svc.update_order_pricing(order_id, client_id, discount, tax, delivery_cost, delivery_provider, note)
                st.success("Saved")
            except Exception as exc:
                st.error(str(exc))

        st.markdown("### Payment block")
        amount = st.number_input("Payment amount", min_value=0.0, value=0.0)
        method = st.text_input("Payment method", value="cash")
        if st.button("Record Payment"):
            try:
                svc.record_payment(order_id, amount, method)
                st.success("Payment recorded")
            except Exception as exc:
                st.error(str(exc))

        st.markdown("### Fulfillment block")
        f1, f2, f3, f4, f5 = st.columns(5)
        if f1.button("Mark Ready to Pack"):
            try:
                svc.mark_ready_to_pack(order_id, user)
                st.success("Ready to pack")
            except Exception as exc:
                st.error(str(exc))
        if f2.button("Mark Packed"):
            try:
                svc.mark_packed(order_id, user)
                st.success("Packed")
            except Exception as exc:
                st.error(str(exc))
        if f3.button("Create Shipment"):
            try:
                svc.create_shipment_for_order(order_id, {"carrier": "manual", "tracking_no": ""}, user)
                st.success("Shipment created")
            except Exception as exc:
                st.error(str(exc))
        if f4.button("Mark Delivered"):
            try:
                svc.mark_delivered(order_id, user)
                st.success("Delivered")
            except Exception as exc:
                st.error(str(exc))
        if f5.button("Mark Delivery Failed"):
            try:
                svc.mark_delivery_failed(order_id, "manual", user)
                st.warning("Delivery failed")
            except Exception as exc:
                st.error(str(exc))

        st.markdown("### Return / Refund block")
        st.info("Use Returns page for detailed return workflow.")

        st.markdown("### Documents block")
        st.write("Invoice and shipment docs available from records.")

        st.markdown("### Timeline / audit log block")
        st.write("Lifecycle events are written in current status and finance/inventory logs.")
