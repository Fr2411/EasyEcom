import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.domain.models.product import ProductPricingUpdate
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService

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
product_svc = ProductService(ProductsRepo(store))
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

st.divider()
st.subheader("Product Pricing Controls")
can_edit_pricing = bool(set(roles).intersection({"SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "FINANCE_ONLY"}))
pricing_products = product_svc.list_by_client(client_id)
if pricing_products.empty:
    st.info("No products available for pricing updates.")
else:
    product_labels = [f"{r.product_id} - {r.product_name}" for r in pricing_products.itertuples(index=False)]
    selected = st.selectbox("Select product to edit pricing", product_labels)
    selected_id = selected.split(" - ")[0]
    current = pricing_products[pricing_products["product_id"] == selected_id].iloc[0]
    with st.form("pricing_editor"):
        selling_price = st.number_input("Default selling price", min_value=0.01, value=float(current.get("default_selling_price") or 0.01), disabled=not can_edit_pricing)
        max_discount = st.number_input("Max discount %", min_value=0.0, max_value=100.0, value=float(current.get("max_discount_pct") or 10.0), disabled=not can_edit_pricing)
        save_pricing = st.form_submit_button("Save pricing", disabled=not can_edit_pricing)
    if not can_edit_pricing:
        st.error("CLIENT_EMPLOYEE cannot edit product pricing.")
    elif save_pricing:
        try:
            product_svc.update_pricing(client_id, selected_id, ProductPricingUpdate(default_selling_price=float(selling_price), max_discount_pct=float(max_discount)))
            st.success("Pricing updated")
        except Exception as exc:
            st.error(str(exc))
