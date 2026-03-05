import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.domain.models.product import ProductCreate
from easy_ecom.domain.services.product_features import parse_features_text
from easy_ecom.domain.services.product_service import ProductService

require_login()
st.title("Products")
store = CsvStore(settings.data_dir)
svc = ProductService(ProductsRepo(store))
client_id = st.session_state["user"]["client_id"]

with st.form("add_product"):
    product_name = st.text_input("Product name")
    supplier = st.text_input("Supplier")
    category = st.text_input("Category", value="General")
    description = st.text_area("Description")
    features = st.text_area(
        "Features",
        help="Enter one feature per line, comma-separated, or with bullet points.",
    )
    default_selling_price = st.number_input("Default selling price", min_value=0.01)
    max_discount_pct = st.number_input("Max discount %", min_value=0.0, max_value=100.0, value=10.0)
    submitted = st.form_submit_button("Add product")

if submitted:
    try:
        parsed_features = parse_features_text(features)
        svc.create(
            ProductCreate(
                client_id=client_id,
                supplier=supplier,
                product_name=product_name,
                category=category,
                prd_description=description,
                prd_features_json=parsed_features,
                default_selling_price=float(default_selling_price),
                max_discount_pct=float(max_discount_pct),
            )
        )
        st.success("Product created")
    except Exception as exc:
        st.error(str(exc))

st.dataframe(svc.list_by_client(client_id))
