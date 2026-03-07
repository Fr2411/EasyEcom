import json

import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.domain.services.catalog_stock_service import CatalogStockService, VariantWorkspaceEntry
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService


def _features_to_text(raw_json: str) -> str:
    if not str(raw_json or "").strip() or str(raw_json).strip() == "{}":
        return ""
    try:
        parsed = json.loads(raw_json)
        values = parsed.get("features", []) if isinstance(parsed, dict) else []
        if isinstance(values, list):
            return "\n".join([str(v) for v in values if str(v).strip()])
    except Exception:
        return str(raw_json)
    return ""


require_login()
roles = st.session_state["user"]["roles"].split(",")
if not can_access_page(roles, "Catalog & Stock"):
    st.error("Access denied")
    st.stop()

store = CsvStore(settings.data_dir)
seq = SequenceService(SequencesRepo(store))
inventory_svc = InventoryService(InventoryTxnRepo(store), seq)
product_svc = ProductService(ProductsRepo(store), ProductVariantsRepo(store))
svc = CatalogStockService(product_svc, inventory_svc)

user = st.session_state["user"]
client_id = user["client_id"]
user_id = user["user_id"]

st.title("Catalog & Stock")
st.caption("Unified workspace to search/create products, manage variants, and post stock.")

st.subheader("Smart Product Entry Workspace")
query = st.text_input(
    "Search existing product or type a new name",
    help="Tenant-scoped lookup. You can free-type to create a brand new product.",
)
suggestions = svc.search_product_names(client_id, query)
selected_match = st.selectbox(
    "Matching products",
    [""] + suggestions,
    index=0,
    help="Optional: choose a match to prefill and edit an existing product.",
)
active_product_name = selected_match.strip() or query.strip()
workspace = svc.load_workspace(client_id, active_product_name)

existing_product = workspace["product"] if workspace["is_existing"] else None
if existing_product is not None:
    st.info(f"Editing existing product: {existing_product['product_name']}")
else:
    st.info("Creating a new product")

with st.form("catalog_stock_form"):
    product_name = st.text_input(
        "Product name",
        value=active_product_name,
        placeholder="Type a product name",
    )
    supplier = st.text_input(
        "Supplier",
        value=str(existing_product.get("supplier", "")) if existing_product else "",
    )
    category = st.text_input(
        "Category",
        value=str(existing_product.get("category", "General")) if existing_product else "General",
    )
    description = st.text_area(
        "Description",
        value=str(existing_product.get("prd_description", "")) if existing_product else "",
    )
    features = st.text_area(
        "Features",
        value=_features_to_text(existing_product.get("prd_features_json", "{}")) if existing_product else "",
        help="One feature per line, comma-separated, or bullet points.",
    )
    c1, c2 = st.columns(2)
    default_selling_price = c1.number_input(
        "Default selling price",
        min_value=0.01,
        value=float(existing_product.get("default_selling_price") or 0.01)
        if existing_product
        else 0.01,
    )
    max_discount_pct = c2.number_input(
        "Max discount %",
        min_value=0.0,
        max_value=100.0,
        value=float(existing_product.get("max_discount_pct") or 10.0) if existing_product else 10.0,
    )

    existing_variants = workspace["variants"] if isinstance(workspace["variants"], list) else []
    default_blocks = max(1, len(existing_variants))
    variant_blocks = st.number_input("Variant blocks", min_value=1, value=default_blocks, step=1)

    entries: list[VariantWorkspaceEntry] = []
    for i in range(int(variant_blocks)):
        seed = existing_variants[i] if i < len(existing_variants) else {}
        st.markdown(f"**Variant {i + 1}**")
        v1, v2, v3 = st.columns(3)
        size = v1.text_input("Size", value=str(seed.get("size", "")), key=f"size_{i}")
        color = v2.text_input("Color", value=str(seed.get("color", "")), key=f"color_{i}")
        other = v3.text_input("Other", value=str(seed.get("other", "")), key=f"other_{i}")
        label_parts = []
        if size.strip():
            label_parts.append(f"Size:{size.strip().title()}")
        if color.strip():
            label_parts.append(f"Color:{color.strip().title()}")
        if other.strip():
            label_parts.append(f"Other:{other.strip().title()}")
        st.caption(f"Label: {' | '.join(label_parts) if label_parts else 'Default'}")

        s1, s2, s3 = st.columns(3)
        qty = s1.number_input("Qty", min_value=0.0, value=0.0, key=f"qty_{i}")
        unit_cost = s2.number_input("Unit cost", min_value=0.0, value=0.0, key=f"cost_{i}")
        lot_reference = s3.text_input("Lot/reference", value="", key=f"lot_ref_{i}")
        s4, s5 = st.columns(2)
        stock_supplier = s4.text_input("Stock supplier", value=supplier, key=f"stock_supplier_{i}")
        received_date = s5.text_input("Received date", value="", key=f"received_{i}")

        entries.append(
            VariantWorkspaceEntry(
                size=size,
                color=color,
                other=other,
                qty=float(qty),
                unit_cost=float(unit_cost),
                lot_reference=lot_reference,
                supplier=stock_supplier,
                received_date=received_date,
            )
        )
        st.divider()

    save = st.form_submit_button("Save Product, Variants & Stock")

if save:
    try:
        product_id, lot_ids, variant_count = svc.save_workspace(
            client_id=client_id,
            user_id=user_id,
            typed_product_name=product_name,
            supplier=supplier,
            category=category,
            description=description,
            features_text=features,
            default_selling_price=float(default_selling_price),
            max_discount_pct=float(max_discount_pct),
            variant_entries=entries,
        )
        st.success(
            f"Saved product {product_id}. Variant upserts: {variant_count}. Stock lots posted: {len(lot_ids)}"
        )
    except Exception as exc:
        st.error(str(exc))

st.subheader("Stock Explorer")
summary, detail = svc.stock_explorer(client_id)
st.dataframe(summary, use_container_width=True)

if not summary.empty:
    selected_row = st.selectbox(
        "Expand product details",
        summary.apply(lambda r: f"{r['product_name']} ({r['product_id']})", axis=1).tolist(),
        index=0,
    )
    selected_id = selected_row.rsplit("(", 1)[1].rstrip(")")
    with st.expander("Variant-level stock detail", expanded=True):
        st.dataframe(detail.get(selected_id), use_container_width=True)
