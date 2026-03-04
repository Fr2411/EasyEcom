import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService

require_login()
roles = st.session_state["user"]["roles"].split(",")
if not can_access_page(roles, "Inventory"):
    st.error("Access denied")
    st.stop()

store = CsvStore(settings.data_dir)
seq = SequenceService(SequencesRepo(store))
svc = InventoryService(InventoryTxnRepo(store), seq)
user = st.session_state["user"]
client_id = user["client_id"]
user_id = user["user_id"]

st.title("Inventory")
products_df = ProductsRepo(store).all()
client_products = products_df[products_df["client_id"] == client_id].copy() if not products_df.empty else products_df
product_options = sorted(client_products["product_name"].dropna().astype(str).unique().tolist()) if not client_products.empty else []

with st.form("stock_in"):
    product_name = st.selectbox("Product name", product_options, index=None, placeholder="Select product")
    qty = st.number_input("Qty", min_value=0.01)
    unit_cost = st.number_input("Unit cost", min_value=0.01)
    supplier = st.text_input("Supplier snapshot")
    note = st.text_input("Note")
    submit = st.form_submit_button("Add stock")
if submit:
    try:
        if not product_name:
            raise ValueError("Please select a product")
        lot_id = svc.add_stock(client_id, product_name, float(qty), float(unit_cost), supplier, note, user_id=user_id)
        st.success(f"Created lot {lot_id}")
    except Exception as exc:
        st.error(str(exc))

st.dataframe(svc.stock_by_lot(client_id))
