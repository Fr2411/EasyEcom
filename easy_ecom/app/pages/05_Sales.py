import streamlit as st
import pandas as pd

from easy_ecom.app.ui.components import require_login
from easy_ecom.app.ui.formatters import format_money
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.data.repos.csv.audit_repo import AuditRepo
from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.customers_repo import CustomersRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, PaymentsRepo, SalesOrderItemsRepo, SalesOrdersRepo, ShipmentsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
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
product_repo = ProductsRepo(store)
product_svc = ProductService(product_repo)
customer_repo = CustomersRepo(store)
client_svc = ClientService(ClientsRepo(store))
svc = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), inv, seq, fin, product_repo, customer_repo, AuditRepo(store))
user = st.session_state["user"]
client_id = user["client_id"]
user_id = user["user_id"]

st.title("Sales")
if st.button("Refresh"):
    st.rerun()
currency_code, currency_symbol = client_svc.get_currency(client_id)

products_df = product_svc.list_by_client(client_id)
product_options = sorted(products_df["product_name"].dropna().astype(str).unique().tolist()) if not products_df.empty else []
product_name = st.selectbox("Product name", product_options, index=None, placeholder="Select product with stock")
selected_product = product_svc.get_by_name(client_id, product_name) if product_name else None
product_id = selected_product["product_id"] if selected_product else ""
qty = st.number_input("Qty", min_value=0.01)
default_price = float(selected_product.get("default_selling_price", 0.01)) if selected_product else 0.01
max_discount_pct = float(selected_product.get("max_discount_pct", 10.0)) if selected_product else 10.0
min_price = default_price * (1 - max_discount_pct / 100)
price = st.number_input("Unit selling price", min_value=0.01, value=default_price)
if product_id:
    st.caption(f"Available stock: {inv.available_qty(client_id, product_id):,.2f}")
    st.caption(f"Minimum allowed price: {format_money(min_price, currency_code, currency_symbol)}")

st.subheader("Customer")
customer_name = st.text_input("Customer name")
matches = customer_repo.find_by_name(client_id, customer_name) if customer_name.strip() else customer_repo.all().iloc[0:0]
matched_customer_id = ""
selected_match = None
if not matches.empty:
    options = [f"{r.customer_id} | {r.full_name} | {r.phone} | {r.email}" for r in matches.itertuples(index=False)]
    selected_label = st.selectbox("Matched customers", options, index=0)
    matched_customer_id = selected_label.split(" | ")[0]
    selected_match = matches[matches["customer_id"] == matched_customer_id].iloc[0]

phone_value = selected_match["phone"] if selected_match is not None else ""
email_value = selected_match["email"] if selected_match is not None else ""
address_value = selected_match["address_line1"] if selected_match is not None else ""
phone = st.text_input("Phone", value=phone_value)
email = st.text_input("Email", value=email_value)
address_line1 = st.text_input("Address", value=address_value)

if st.button("Confirm sale"):
    try:
        if not product_id:
            raise ValueError("Please select a product")
        if float(price) < min_price:
            raise ValueError(f"Unit price cannot be below {format_money(min_price, currency_code, currency_symbol)}")

        resolved_customer_id = svc.resolve_customer_for_sale(
            client_id,
            {
                "full_name": customer_name,
                "phone": phone,
                "email": email,
                "address_line1": address_line1,
            },
            matched_customer_id=matched_customer_id,
            user_id=user_id,
        )

        payload = SaleConfirm(client_id=client_id, customer_id=resolved_customer_id, items=[SaleItem(product_id=product_id, qty=float(qty), unit_selling_price=float(price))])
        result = svc.confirm_sale(payload, {"full_name": customer_name, "phone": phone, "address_line1": address_line1}, user_id=user_id)
        st.success(f"Order confirmed {result['order_id']}")
    except Exception as exc:
        st.error(str(exc))

st.subheader("Sales records")
orders_df = SalesOrdersRepo(store).all().copy()
invoices_df = InvoicesRepo(store).all().copy()
payments_df = PaymentsRepo(store).all().copy()
customers_df = customer_repo.all().copy()

client_orders = orders_df[orders_df["client_id"] == client_id].copy() if not orders_df.empty else pd.DataFrame()
if client_orders.empty:
    st.info("No sales records found for this client yet.")
else:
    invoice_cols = ["order_id", "invoice_no", "invoice_id", "status"]
    if not invoices_df.empty:
        invoices_df = invoices_df[invoices_df["client_id"] == client_id].copy()
    else:
        invoices_df = pd.DataFrame(columns=invoice_cols)
    invoice_view = invoices_df[invoice_cols] if all(col in invoices_df.columns for col in invoice_cols) else pd.DataFrame(columns=invoice_cols)
    invoice_view = invoice_view.rename(columns={"status": "invoice_status"})

    if not payments_df.empty and not invoices_df.empty:
        client_payments = payments_df[payments_df["client_id"] == client_id].copy()
        payment_totals = client_payments.groupby("invoice_id", as_index=False)["amount_paid"].sum()
        payment_totals["amount_paid"] = payment_totals["amount_paid"].astype(float)
    else:
        payment_totals = pd.DataFrame(columns=["invoice_id", "amount_paid"])

    records = client_orders.merge(invoice_view, on="order_id", how="left")
    records = records.merge(payment_totals, on="invoice_id", how="left")
    records["amount_paid"] = records["amount_paid"].fillna(0.0)

    customer_view = customers_df[["customer_id", "full_name"]] if not customers_df.empty else pd.DataFrame(columns=["customer_id", "full_name"])
    records = records.merge(customer_view, on="customer_id", how="left")
    records["full_name"] = records["full_name"].fillna("")

    records["subtotal"] = records["subtotal"].astype(float)
    records["grand_total"] = records["grand_total"].astype(float)
    records["balance_due"] = (records["grand_total"] - records["amount_paid"]).clip(lower=0.0)
    records["timestamp"] = pd.to_datetime(records["timestamp"], errors="coerce")
    records = records.sort_values("timestamp", ascending=False)

    records["invoice_status"] = records.get("invoice_status", pd.Series("", index=records.index)).fillna("")

    display_df = records[["timestamp", "order_id", "invoice_no", "full_name", "invoice_status", "grand_total", "amount_paid", "balance_due"]].copy()
    display_df = display_df.rename(columns={"full_name": "customer_name"})
    display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    for amount_col in ["grand_total", "amount_paid", "balance_due"]:
        display_df[amount_col] = display_df[amount_col].apply(lambda amount: format_money(float(amount), currency_code, currency_symbol))

    st.dataframe(display_df, use_container_width=True)
