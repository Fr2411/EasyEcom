import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.domain.models.product import ProductPricingUpdate
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService
from easy_ecom.domain.services.data_reconciliation_service import DataReconciliationService
from easy_ecom.data.repos.csv.sales_repo import SalesOrderItemsRepo, SalesOrdersRepo
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo

require_login()
roles = st.session_state["user"]["roles"].split(",")
if not can_access_page(roles, "Inventory"):
    st.error("Access denied")
    st.stop()

store = CsvStore(settings.data_dir)
seq = SequenceService(SequencesRepo(store))
svc = InventoryService(InventoryTxnRepo(store), seq)
recon = DataReconciliationService(
    InventoryTxnRepo(store),
    ProductsRepo(store),
    SalesOrdersRepo(store),
    SalesOrderItemsRepo(store),
    LedgerRepo(store),
)
user = st.session_state["user"]
client_id = user["client_id"]
user_id = user["user_id"]

st.title("Inventory")
product_svc = ProductService(ProductsRepo(store), ProductVariantsRepo(store))
client_products = product_svc.list_by_client(client_id)
product_options = (
    sorted(client_products["product_name"].dropna().astype(str).unique().tolist())
    if not client_products.empty
    else []
)

parent_name = st.selectbox("Parent product", product_options, index=None)
if parent_name:
    parent = product_svc.get_by_name(client_id, parent_name)
    variants = product_svc.list_variants(client_id, parent["product_id"])
    st.caption("Stock-in by variant")
    same_cost = st.checkbox("Same unit cost for all variants", value=True)
    common_cost = st.number_input("Unit cost", min_value=0.01, value=0.01) if same_cost else 0.0
    with st.form("stock_in_variants"):
        entries = []
        for variant in variants:
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(variant["variant_name"])
            qty = c2.number_input("Qty", min_value=0.0, key=f"qty_{variant['variant_id']}")
            unit_cost = (
                common_cost
                if same_cost
                else c3.number_input(
                    "Unit cost", min_value=0.01, key=f"cost_{variant['variant_id']}"
                )
            )
            entries.append((variant, qty, unit_cost))
        submit = st.form_submit_button("Add stock")
    if submit:
        for variant, qty, unit_cost in entries:
            if qty > 0:
                svc.add_stock(
                    client_id,
                    variant["variant_id"],
                    variant["variant_name"],
                    float(qty),
                    float(unit_cost),
                    "",
                    "",
                    user_id=user_id,
                )
        st.success("Stock posted")

stock_rows = svc.stock_by_lot_with_issues(client_id)
st.dataframe(
    stock_rows[["product_name", "product_id", "lot_id", "qty", "unit_cost"]],
    use_container_width=True,
)

if "SUPER_ADMIN" in roles:
    unmapped = stock_rows[stock_rows["is_unmapped"]]
    if not unmapped.empty:
        st.warning(
            "Unmapped inventory rows detected. These are included in totals but need data repair."
        )
        st.dataframe(
            unmapped[["product_name", "product_id", "lot_id", "qty", "unit_cost", "issue_reason"]],
            use_container_width=True,
        )
    issues = recon.integrity_issues(client_id)
    if issues:
        st.subheader("Data issues (admin)")
        st.dataframe(
            [
                {
                    "type": i.issue_type,
                    "severity": i.severity,
                    "reference": i.reference_id,
                    "message": i.message,
                }
                for i in issues
            ],
            use_container_width=True,
        )

st.divider()
st.subheader("Product Pricing Controls")
can_edit_pricing = bool(
    set(roles).intersection({"SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "FINANCE_ONLY"})
)
pricing_products = product_svc.list_by_client(client_id)
if not pricing_products.empty:
    selected = st.selectbox(
        "Select product to edit pricing",
        [f"{r.product_id} - {r.product_name}" for r in pricing_products.itertuples(index=False)],
    )
    selected_id = selected.split(" - ")[0]
    current = pricing_products[pricing_products["product_id"] == selected_id].iloc[0]
    with st.form("pricing_editor"):
        selling_price = st.number_input(
            "Default selling price",
            min_value=0.01,
            value=float(current.get("default_selling_price") or 0.01),
            disabled=not can_edit_pricing,
        )
        max_discount = st.number_input(
            "Max discount %",
            min_value=0.0,
            max_value=100.0,
            value=float(current.get("max_discount_pct") or 10.0),
            disabled=not can_edit_pricing,
        )
        save_pricing = st.form_submit_button("Save pricing", disabled=not can_edit_pricing)
    if save_pricing and can_edit_pricing:
        product_svc.update_pricing(
            client_id,
            selected_id,
            ProductPricingUpdate(
                default_selling_price=float(selling_price), max_discount_pct=float(max_discount)
            ),
        )
        st.success("Pricing updated")
