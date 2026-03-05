import streamlit as st

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
