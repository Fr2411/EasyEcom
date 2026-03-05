import pandas as pd
import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.domain.models.product import ProductCreate
from easy_ecom.domain.services.product_features import parse_features_text
from easy_ecom.domain.services.product_service import ProductService

require_login()
st.title("Products")
store = CsvStore(settings.data_dir)
svc = ProductService(ProductsRepo(store), ProductVariantsRepo(store))
client_id = st.session_state["user"]["client_id"]

with st.form("add_product"):
    product_name = st.text_input("Product name")
    supplier = st.text_input("Supplier")
    category = st.text_input("Category", value="General")
    description = st.text_area("Description")
    features = st.text_area("Features", help="Enter one feature per line, comma-separated, or with bullet points.")
    default_selling_price = st.number_input("Default selling price", min_value=0.01)
    max_discount_pct = st.number_input("Max discount %", min_value=0.0, max_value=100.0, value=10.0)
    sizes_csv = st.text_input("Sizes (comma separated)")
    colors_csv = st.text_input("Colors (comma separated)")
    others_csv = st.text_input("Other variants (comma separated)")
    submitted = st.form_submit_button("Add product")

if submitted:
    try:
        product_id = svc.create(ProductCreate(client_id=client_id, supplier=supplier, product_name=product_name, category=category, prd_description=description, prd_features_json=parse_features_text(features), default_selling_price=float(default_selling_price), max_discount_pct=float(max_discount_pct), sizes_csv=sizes_csv, colors_csv=colors_csv, others_csv=others_csv))
        st.success(f"Product created: {product_id}")
    except Exception as exc:
        st.error(str(exc))

products = svc.list_by_client(client_id)
st.dataframe(products, use_container_width=True)
if not products.empty:
    selected = st.selectbox("Select parent product for variant generation", products["product_name"].tolist(), index=None)
    if selected:
        product = svc.get_by_name(client_id, selected)
        size_v = st.text_input("Generate sizes", value=product.get("sizes_csv", ""))
        color_v = st.text_input("Generate colors", value=product.get("colors_csv", ""))
        other_v = st.text_input("Generate others", value=product.get("others_csv", ""))
        preview = pd.DataFrame(svc.generate_variants(client_id, product["product_id"], size_v, color_v, other_v)) if st.button("Generate Variants") else pd.DataFrame()
        if not preview.empty:
            st.dataframe(preview, use_container_width=True)
        variants = pd.DataFrame(svc.list_variants(client_id, product["product_id"]))
        if not variants.empty:
            st.subheader("Variants")
            st.dataframe(variants, use_container_width=True)
