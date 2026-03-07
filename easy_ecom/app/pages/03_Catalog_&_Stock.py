import pandas as pd
import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.domain.services.catalog_stock_service import (
    CatalogStockService,
    VariantWorkspaceEntry,
)
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService


def _variant_rows_from_workspace(workspace: dict[str, object]) -> list[dict[str, object]]:
    product = workspace.get("product") if isinstance(workspace.get("product"), dict) else {}
    base_price = float(product.get("default_selling_price") or 0.0) if product else 0.0
    base_discount = float(product.get("max_discount_pct") or 10.0) if product else 10.0
    variants = workspace.get("variants") if isinstance(workspace.get("variants"), list) else []
    rows: list[dict[str, object]] = []
    for row in variants:
        rows.append(
            {
                "variant_id": str(row.get("variant_id", "")),
                "variant_label": str(row.get("variant_name", "") or ""),
                "size": str(row.get("size", "") or ""),
                "color": str(row.get("color", "") or ""),
                "other": str(row.get("other", "") or ""),
                "qty": 0.0,
                "cost": 0.0,
                "selling_price": float(row.get("default_selling_price") or base_price),
                "max_discount_pct": float(row.get("max_discount_pct") or base_discount),
                "remove": False,
            }
        )
    return rows


def _blank_variant_row(default_price: float, max_discount_pct: float) -> dict[str, object]:
    return {
        "variant_id": "",
        "variant_label": "",
        "size": "",
        "color": "",
        "other": "",
        "qty": 0.0,
        "cost": 0.0,
        "selling_price": float(default_price),
        "max_discount_pct": float(max_discount_pct),
        "remove": False,
    }


def _normalize_editor_df(
    editor_value: object, default_price: float, max_discount_pct: float
) -> pd.DataFrame:
    if isinstance(editor_value, pd.DataFrame):
        df = editor_value.copy()
    elif isinstance(editor_value, list):
        df = pd.DataFrame(editor_value)
    else:
        df = pd.DataFrame()
    if df.empty:
        df = pd.DataFrame([_blank_variant_row(default_price, max_discount_pct)])

    defaults = {
        "variant_id": "",
        "variant_label": "",
        "size": "",
        "color": "",
        "other": "",
        "qty": 0.0,
        "cost": 0.0,
        "selling_price": float(default_price),
        "max_discount_pct": float(max_discount_pct),
        "remove": False,
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    df = df[list(defaults.keys())].copy()
    for text_col in ["variant_id", "variant_label", "size", "color", "other"]:
        df[text_col] = df[text_col].fillna("").astype(str)
    for num_col in ["qty", "cost", "selling_price", "max_discount_pct"]:
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0.0)
    df["remove"] = df["remove"].fillna(False).astype(bool)
    return df


def _sync_variant_labels(df: pd.DataFrame, product_svc: ProductService) -> pd.DataFrame:
    synced = df.copy()
    for idx, row in synced.iterrows():
        label = str(row.get("variant_label", "")).strip()
        size = str(row.get("size", "")).strip().title()
        color = str(row.get("color", "")).strip().title()
        other = str(row.get("other", "")).strip().title()
        if not label:
            label = product_svc._variant_name(size, color, other)
        synced.at[idx, "size"] = size
        synced.at[idx, "color"] = color
        synced.at[idx, "other"] = other
        synced.at[idx, "variant_label"] = label
    return synced


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
st.caption("Compact workspace to search/add product, edit variants, and post stock in one flow.")

query = st.text_input("Search or add product", placeholder="Type to search...", key="catalog_query")
search_term = query.strip()
add_option = f'Add new product: "{search_term or "New Product"}"'
suggestions = svc.suggest_products(client_id, search_term)
option_map = {add_option: ""}
for item in suggestions:
    option_map[f"{item['product_name']} ({item['product_id'][:8]})"] = str(item["product_id"])

choice = st.selectbox("Select product", options=list(option_map.keys()), key="catalog_choice")
selected_product_id = option_map.get(choice, "")
workspace = svc.load_workspace(client_id, search_term, selected_product_id)
is_existing = bool(workspace["is_existing"])
product = workspace["product"] if isinstance(workspace["product"], dict) else {}
resolved_name = str(product.get("product_name", "")).strip() if is_existing else search_term

selection_token = f"{selected_product_id}|{resolved_name}|{is_existing}"
if st.session_state.get("catalog_selection_token") != selection_token:
    st.session_state["catalog_selection_token"] = selection_token
    st.session_state["catalog_product_name"] = resolved_name
    st.session_state["catalog_supplier"] = str(product.get("supplier", "")) if product else ""
    st.session_state["catalog_category"] = (
        str(product.get("category", "General")) if product else "General"
    )
    st.session_state["catalog_description"] = (
        str(product.get("prd_description", "")) if product else ""
    )
    st.session_state["catalog_features"] = (
        svc.features_to_text(str(product.get("prd_features_json", "{}"))) if product else ""
    )
    st.session_state["catalog_default_price"] = (
        float(product.get("default_selling_price") or 0.0) if product else 0.0
    )
    st.session_state["catalog_max_discount"] = (
        float(product.get("max_discount_pct") or 10.0) if product else 10.0
    )
    rows = _variant_rows_from_workspace(workspace)
    st.session_state["catalog_variant_rows"] = rows or [
        _blank_variant_row(
            st.session_state["catalog_default_price"], st.session_state["catalog_max_discount"]
        )
    ]

if is_existing:
    st.success(f"Existing product mode: {resolved_name}")
else:
    st.info("New product mode")

supplier_options = list(dict.fromkeys(workspace["supplier_options"] + ["+ Add new supplier..."]))
category_options = list(dict.fromkeys(workspace["category_options"] + ["+ Add new category..."]))

info_col1, info_col2, info_col3 = st.columns([2, 1.3, 1.3])
with info_col1:
    product_name = st.text_input("Product Name", key="catalog_product_name")
with info_col2:
    supplier_choice = st.selectbox(
        "Supplier",
        options=supplier_options,
        index=(
            supplier_options.index(st.session_state["catalog_supplier"])
            if st.session_state["catalog_supplier"] in supplier_options
            else 0
        ),
        key="catalog_supplier_choice",
    )
    supplier = (
        st.text_input("New Supplier", key="catalog_supplier")
        if supplier_choice == "+ Add new supplier..."
        else supplier_choice
    )
with info_col3:
    category_choice = st.selectbox(
        "Category",
        options=category_options,
        index=(
            category_options.index(st.session_state["catalog_category"])
            if st.session_state["catalog_category"] in category_options
            else 0
        ),
        key="catalog_category_choice",
    )
    category = (
        st.text_input("New Category", key="catalog_category")
        if category_choice == "+ Add new category..."
        else category_choice
    )

meta_col1, meta_col2, meta_col3, meta_col4 = st.columns([2, 2, 1, 1])
with meta_col1:
    description = st.text_input("Description", key="catalog_description")
with meta_col2:
    features = st.text_input("Features (comma-separated)", key="catalog_features")
with meta_col3:
    default_selling_price = st.number_input(
        "Default Selling Price", min_value=0.0, key="catalog_default_price"
    )
with meta_col4:
    max_discount_pct = st.number_input(
        "Max Discount %",
        min_value=0.0,
        max_value=100.0,
        key="catalog_max_discount",
    )

if is_existing:
    action_cols = st.columns([1, 4])
    if action_cols[0].button("Add Variant", use_container_width=True):
        rows = list(st.session_state.get("catalog_variant_rows", []))
        rows.append(_blank_variant_row(default_selling_price, max_discount_pct))
        st.session_state["catalog_variant_rows"] = rows
else:
    gen_cols = st.columns([1.2, 1.2, 1.2, 1])
    sizes_csv = gen_cols[0].text_input("size values", key="catalog_sizes_csv")
    colors_csv = gen_cols[1].text_input("color values", key="catalog_colors_csv")
    others_csv = gen_cols[2].text_input("other values", key="catalog_others_csv")
    if gen_cols[3].button("Generate Variants", use_container_width=True):
        generated = svc.generate_variant_rows(
            sizes_csv=sizes_csv,
            colors_csv=colors_csv,
            others_csv=others_csv,
            default_selling_price=default_selling_price,
            max_discount_pct=max_discount_pct,
        )
        existing_rows = _normalize_editor_df(
            st.session_state.get("catalog_variant_rows", []),
            default_selling_price,
            max_discount_pct,
        )
        existing_keys = {
            f"{r['size'].strip().lower()}|{r['color'].strip().lower()}|{r['other'].strip().lower()}"
            for _, r in existing_rows.iterrows()
        }
        merged = existing_rows.to_dict(orient="records")
        for row in generated:
            key = f"{row.size.strip().lower()}|{row.color.strip().lower()}|{row.other.strip().lower()}"
            if key in existing_keys:
                continue
            merged.append(
                {
                    "variant_id": "",
                    "variant_label": row.variant_label,
                    "size": row.size,
                    "color": row.color,
                    "other": row.other,
                    "qty": 0.0,
                    "cost": 0.0,
                    "selling_price": row.default_selling_price,
                    "max_discount_pct": row.max_discount_pct,
                    "remove": False,
                }
            )
        st.session_state["catalog_variant_rows"] = merged

same_cost = st.checkbox("Same cost for all variants", key="catalog_same_cost")
if same_cost:
    cost_cols = st.columns([1, 1, 5])
    shared_cost = cost_cols[0].number_input("Shared Cost", min_value=0.0, key="catalog_shared_cost")
    if cost_cols[1].button("Apply", use_container_width=True):
        current = _normalize_editor_df(
            st.session_state.get("catalog_variant_rows", []),
            default_selling_price,
            max_discount_pct,
        )
        entries = [
            VariantWorkspaceEntry(
                variant_id=str(r.get("variant_id", "")),
                variant_label=str(r.get("variant_label", "")),
                size=str(r.get("size", "")),
                color=str(r.get("color", "")),
                other=str(r.get("other", "")),
                qty=float(r.get("qty", 0.0)),
                unit_cost=float(r.get("cost", 0.0)),
                default_selling_price=float(r.get("selling_price", default_selling_price)),
                max_discount_pct=float(r.get("max_discount_pct", max_discount_pct)),
            )
            for _, r in current.iterrows()
        ]
        updated = svc.apply_shared_cost(entries, shared_cost)
        st.session_state["catalog_variant_rows"] = [
            {
                "variant_id": r.variant_id,
                "variant_label": r.variant_label,
                "size": r.size,
                "color": r.color,
                "other": r.other,
                "qty": r.qty,
                "cost": r.unit_cost,
                "selling_price": r.default_selling_price,
                "max_discount_pct": r.max_discount_pct,
                "remove": False,
            }
            for r in updated
        ]

editor_seed = _normalize_editor_df(
    st.session_state.get("catalog_variant_rows", []), default_selling_price, max_discount_pct
)
variant_df = st.data_editor(
    editor_seed,
    use_container_width=True,
    num_rows="dynamic",
    hide_index=True,
    column_config={
        "variant_id": st.column_config.TextColumn("Variant ID", disabled=True, width="small"),
        "variant_label": st.column_config.TextColumn(
            "Variant label", required=False, width="medium"
        ),
        "size": st.column_config.TextColumn("Size", width="small"),
        "color": st.column_config.TextColumn("Color", width="small"),
        "other": st.column_config.TextColumn("Other", width="small"),
        "qty": st.column_config.NumberColumn("Qty", min_value=0.0, step=1.0, width="small"),
        "cost": st.column_config.NumberColumn("Cost", min_value=0.0, step=0.01, width="small"),
        "selling_price": st.column_config.NumberColumn(
            "Default Selling Price", min_value=0.0, step=0.01
        ),
        "max_discount_pct": st.column_config.NumberColumn(
            "Max Discount %", min_value=0.0, max_value=100.0, step=0.5
        ),
        "remove": st.column_config.CheckboxColumn("Remove"),
    },
    key="catalog_variant_editor",
)

variant_df = _sync_variant_labels(
    _normalize_editor_df(variant_df, default_selling_price, max_discount_pct),
    product_svc,
)
st.session_state["catalog_variant_rows"] = variant_df.to_dict(orient="records")

live_rows = variant_df[~variant_df["remove"]].copy()
variant_count = int(len(live_rows))
total_qty = float(live_rows["qty"].sum())
estimated_stock_cost = float((live_rows["qty"] * live_rows["cost"]).sum())
st.caption(
    f"Summary: {variant_count} variants | total qty to post: {total_qty:.0f} | estimated stock cost: {estimated_stock_cost:.2f}"
)

if st.button("Save", type="primary", use_container_width=True):
    save_df = live_rows.copy()
    if bool(same_cost):
        shared_cost = float(st.session_state.get("catalog_shared_cost", 0.0))
        save_df.loc[save_df["cost"] <= 0, "cost"] = shared_cost

    entries = [
        VariantWorkspaceEntry(
            variant_id=str(r.get("variant_id", "")),
            variant_label=str(r.get("variant_label", "")),
            size=str(r.get("size", "")),
            color=str(r.get("color", "")),
            other=str(r.get("other", "")),
            qty=float(r.get("qty", 0.0)),
            unit_cost=float(r.get("cost", 0.0)),
            default_selling_price=float(r.get("selling_price", default_selling_price)),
            max_discount_pct=float(r.get("max_discount_pct", max_discount_pct)),
            lot_reference="",
            supplier=str(supplier),
            received_date="",
        )
        for _, r in save_df.iterrows()
    ]

    try:
        product_id, lot_ids, variant_upserts = svc.save_workspace(
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
            selected_product_id=selected_product_id,
        )
        st.success(
            f"Saved product {product_id}. Variant upserts: {variant_upserts}. Stock lots posted: {len(lot_ids)}"
        )
    except Exception as exc:
        st.error(str(exc))
