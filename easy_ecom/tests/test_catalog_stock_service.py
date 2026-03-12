from pathlib import Path

from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.domain.models.product import ProductCreate
from easy_ecom.domain.services.catalog_stock_service import (
    CatalogStockService,
    VariantWorkspaceEntry,
)
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService


def setup_store(tmp_path: Path):
    store = CsvStore(tmp_path)
    for table, cols in TABLE_SCHEMAS.items():
        store.ensure_table(table, cols)
    return store


def _service(tmp_path: Path):
    store = setup_store(tmp_path)
    product_svc = ProductService(ProductsRepo(store), ProductVariantsRepo(store))
    inv_svc = InventoryService(InventoryTxnRepo(store), SequenceService(SequencesRepo(store)))
    svc = CatalogStockService(product_svc, inv_svc)
    return svc, product_svc, inv_svc


def test_existing_product_workspace_loads_existing_variants(tmp_path: Path):
    svc, product_svc, _ = _service(tmp_path)
    product_id = product_svc.create(
        ProductCreate(
            client_id="c1",
            supplier="s",
            product_name="Tee",
            default_selling_price=100,
            max_discount_pct=10,
            sizes_csv="M,L",
            colors_csv="Red",
            others_csv="",
        )
    )

    workspace = svc.load_workspace("c1", "tee", product_id)

    assert workspace["is_existing"] is True
    assert workspace["product"]["product_id"] == product_id
    assert len(workspace["variants"]) == 2


def test_existing_product_mode_can_add_new_variant(tmp_path: Path):
    svc, product_svc, _ = _service(tmp_path)
    product_id = product_svc.create(
        ProductCreate(
            client_id="c1",
            supplier="s",
            product_name="Shirt",
            default_selling_price=50,
            max_discount_pct=8,
            sizes_csv="M",
            colors_csv="Blue",
            others_csv="",
        )
    )

    _, _, upserts = svc.save_workspace(
        client_id="c1",
        user_id="u1",
        typed_product_name="Shirt",
        supplier="s",
        category="General",
        description="",
        features_text="",
        default_selling_price=55,
        max_discount_pct=9,
        selected_product_id=product_id,
        variant_entries=[VariantWorkspaceEntry(size="L", color="Blue", qty=0, unit_cost=0)],
    )

    variants = product_svc.list_variants("c1", product_id)
    assert upserts == 1
    assert any(v["size"] == "L" and v["color"] == "Blue" for v in variants)


def test_new_product_mode_generates_variants_from_option_axes(tmp_path: Path):
    svc, _, _ = _service(tmp_path)

    rows = svc.generate_variant_rows(
        sizes_csv="s,m",
        colors_csv="red,blue",
        others_csv="cotton",
        default_selling_price=120,
        max_discount_pct=10,
    )

    keys = {(r.size, r.color, r.other) for r in rows}
    assert len(rows) == 4
    assert ("S", "Red", "Cotton") in keys
    assert ("M", "Blue", "Cotton") in keys


def test_duplicate_variant_prevention_and_stock_posting_only_for_positive_qty(tmp_path: Path):
    svc, product_svc, inv_svc = _service(tmp_path)

    product_id, lots, upserts = svc.save_workspace(
        client_id="c1",
        user_id="u1",
        typed_product_name="TEE",
        supplier="s1",
        category="General",
        description="desc",
        features_text="feature 1",
        default_selling_price=100.0,
        max_discount_pct=10.0,
        variant_entries=[
            VariantWorkspaceEntry(size="M", color="Red", qty=0, unit_cost=20),
            VariantWorkspaceEntry(size="M", color="Red", qty=2, unit_cost=22),
        ],
    )

    variants = product_svc.list_variants("c1", product_id)
    red_variants = [v for v in variants if v.get("size") == "M" and v.get("color") == "Red"]
    stock = inv_svc.stock_by_lot_with_issues("c1")

    assert upserts == 2
    assert len(red_variants) == 1
    assert len(lots) == 1
    assert float(stock[stock["variant_id"] == red_variants[0]["variant_id"]].iloc[0]["qty"]) == 2.0


def test_same_cost_helper_applies_only_to_empty_cost_rows(tmp_path: Path):
    svc, _, _ = _service(tmp_path)
    rows = [
        VariantWorkspaceEntry(size="S", color="Red", unit_cost=0),
        VariantWorkspaceEntry(size="M", color="Red", unit_cost=50),
    ]

    updated = svc.apply_shared_cost(rows, 30)

    assert float(updated[0].unit_cost) == 30.0
    assert float(updated[1].unit_cost) == 50.0


def test_save_and_workspace_flow_remains_tenant_scoped(tmp_path: Path):
    svc, product_svc, _ = _service(tmp_path)
    product_a = product_svc.create(
        ProductCreate(
            client_id="cA",
            supplier="s",
            product_name="Shared Name",
            default_selling_price=100,
            max_discount_pct=10,
            sizes_csv="",
            colors_csv="",
            others_csv="",
        )
    )
    product_svc.create(
        ProductCreate(
            client_id="cB",
            supplier="s",
            product_name="Shared Name",
            default_selling_price=100,
            max_discount_pct=10,
            sizes_csv="",
            colors_csv="",
            others_csv="",
        )
    )

    workspace = svc.load_workspace("cA", "shared", product_a)
    assert workspace["product"]["client_id"] == "cA"

    product_id, _, _ = svc.save_workspace(
        client_id="cA",
        user_id="u1",
        typed_product_name="Shared Name",
        supplier="supplier-a",
        category="A",
        description="desc",
        features_text="feature",
        default_selling_price=110.0,
        max_discount_pct=15.0,
        variant_entries=[VariantWorkspaceEntry(size="X", color="Black", qty=0, unit_cost=0)],
        selected_product_id=product_a,
    )

    assert product_id == product_a
    updated = product_svc.get_by_id("cA", product_a)
    other_tenant = product_svc.get_by_name_ci("cB", "Shared Name")
    assert updated["supplier"] == "supplier-a"
    assert other_tenant["supplier"] == "s"


def test_new_product_with_blank_variant_rows_auto_creates_default_variant(tmp_path: Path):
    svc, product_svc, _ = _service(tmp_path)

    product_id, lots, upserts = svc.save_workspace(
        client_id="c1",
        user_id="u1",
        typed_product_name="Bottle",
        supplier="s1",
        category="General",
        description="",
        features_text="",
        default_selling_price=35.0,
        max_discount_pct=5.0,
        variant_entries=[VariantWorkspaceEntry()],
    )

    variants = product_svc.list_variants("c1", product_id)
    assert upserts == 1
    assert len(variants) == 1
    assert variants[0]["variant_name"] == "Bottle | Default"
    assert lots == []


def test_new_product_with_opening_stock_and_blank_variant_fields_posts_stock_for_default_variant(tmp_path: Path):
    svc, product_svc, inv_svc = _service(tmp_path)

    product_id, lots, upserts = svc.save_workspace(
        client_id="c1",
        user_id="u1",
        typed_product_name="Jar",
        supplier="s1",
        category="General",
        description="",
        features_text="",
        default_selling_price=20.0,
        max_discount_pct=5.0,
        variant_entries=[VariantWorkspaceEntry(qty=4, unit_cost=3)],
    )

    variants = product_svc.list_variants("c1", product_id)
    assert upserts == 1
    assert len(variants) == 1

    txns = inv_svc.repo.all()
    assert len(lots) == 1
    assert len(txns) == 1
    assert txns.iloc[0]["txn_type"] == "IN"
    assert txns.iloc[0]["variant_id"] == variants[0]["variant_id"]
    assert txns.iloc[0]["product_id"] == product_id


def test_new_product_with_multiple_variant_opening_stock_posts_each_variant(tmp_path: Path):
    svc, product_svc, inv_svc = _service(tmp_path)

    product_id, lots, upserts = svc.save_workspace(
        client_id="c1",
        user_id="u1",
        typed_product_name="Sneaker",
        supplier="s1",
        category="General",
        description="",
        features_text="",
        default_selling_price=80.0,
        max_discount_pct=10.0,
        variant_entries=[
            VariantWorkspaceEntry(size="M", color="Red", qty=2, unit_cost=20),
            VariantWorkspaceEntry(size="L", color="Blue", qty=3, unit_cost=25),
        ],
    )

    variants = product_svc.list_variants("c1", product_id)
    txns = inv_svc.repo.all()

    assert upserts == 2
    assert len(variants) == 2
    assert len(lots) == 2
    assert len(txns) == 2


def test_variant_name_starts_with_product_name(tmp_path: Path):
    svc, product_svc, _ = _service(tmp_path)

    product_id, _, _ = svc.save_workspace(
        client_id="c1",
        user_id="u1",
        typed_product_name="Bottle",
        supplier="s1",
        category="General",
        description="",
        features_text="",
        default_selling_price=35.0,
        max_discount_pct=5.0,
        variant_entries=[VariantWorkspaceEntry(size="M", color="Green")],
    )

    variants = product_svc.list_variants("c1", product_id)
    assert variants[0]["variant_name"].startswith("Bottle | ")


def test_save_workspace_persists_distinct_variant_attributes(tmp_path: Path):
    svc, product_svc, _ = _service(tmp_path)

    product_id, _, upserts = svc.save_workspace(
        client_id="c1",
        user_id="u1",
        typed_product_name="Attribute Tee",
        supplier="s1",
        category="General",
        description="",
        features_text="",
        default_selling_price=100.0,
        max_discount_pct=10.0,
        variant_entries=[
            VariantWorkspaceEntry(size="S", color="", other="", qty=0, unit_cost=0),
            VariantWorkspaceEntry(size="M", color="", other="", qty=0, unit_cost=0),
            VariantWorkspaceEntry(size="", color="Black", other="", qty=0, unit_cost=0),
            VariantWorkspaceEntry(size="", color="White", other="", qty=0, unit_cost=0),
            VariantWorkspaceEntry(size="L", color="Black", other="", qty=0, unit_cost=0),
            VariantWorkspaceEntry(size="L", color="White", other="", qty=0, unit_cost=0),
        ],
    )

    variants = product_svc.list_variants("c1", product_id)
    keys = {(v.get("size", ""), v.get("color", ""), v.get("other", "")) for v in variants}

    assert upserts == 6
    assert len(variants) == 6
    assert ("S", "", "") in keys
    assert ("M", "", "") in keys
    assert ("", "Black", "") in keys
    assert ("", "White", "") in keys
    assert ("L", "Black", "") in keys
    assert ("L", "White", "") in keys
