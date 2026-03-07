from pathlib import Path

from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.domain.models.product import ProductCreate
from easy_ecom.domain.services.catalog_stock_service import CatalogStockService, VariantWorkspaceEntry
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService


def setup_store(tmp_path: Path):
    store = CsvStore(tmp_path)
    for table, cols in TABLE_SCHEMAS.items():
        store.ensure_table(table, cols)
    return store


def test_catalog_stock_creates_or_updates_product_and_upserts_variants(tmp_path: Path):
    store = setup_store(tmp_path)
    product_svc = ProductService(ProductsRepo(store), ProductVariantsRepo(store))
    inv_svc = InventoryService(InventoryTxnRepo(store), SequenceService(SequencesRepo(store)))
    svc = CatalogStockService(product_svc, inv_svc)

    product_id, lots, upserts = svc.save_workspace(
        client_id="c1",
        user_id="u1",
        typed_product_name="tee",
        supplier="s1",
        category="General",
        description="desc",
        features_text="feature 1",
        default_selling_price=100.0,
        max_discount_pct=10.0,
        variant_entries=[
            VariantWorkspaceEntry(size="M", color="Red", qty=5, unit_cost=20, lot_reference="L-1")
        ],
    )
    assert product_id
    assert len(lots) == 1
    assert upserts == 1

    product_id_2, lots_2, upserts_2 = svc.save_workspace(
        client_id="c1",
        user_id="u1",
        typed_product_name="TEE",
        supplier="s2",
        category="Apparel",
        description="desc2",
        features_text="feature 2",
        default_selling_price=150.0,
        max_discount_pct=12.0,
        variant_entries=[
            VariantWorkspaceEntry(size="M", color="Red", qty=2, unit_cost=22, lot_reference="L-2")
        ],
    )

    assert product_id_2 == product_id
    assert upserts_2 == 1
    assert len(lots_2) == 1
    variants = product_svc.list_variants("c1", product_id)
    red_variants = [v for v in variants if v.get("size") == "M" and v.get("color") == "Red"]
    assert len(red_variants) == 1


def test_catalog_stock_explorer_rollup_is_parent_level(tmp_path: Path):
    store = setup_store(tmp_path)
    product_svc = ProductService(ProductsRepo(store), ProductVariantsRepo(store))
    inv_svc = InventoryService(InventoryTxnRepo(store), SequenceService(SequencesRepo(store)))
    svc = CatalogStockService(product_svc, inv_svc)

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
    variants = product_svc.list_variants("c1", product_id)
    inv_svc.add_stock("c1", variants[0]["variant_id"], variants[0]["variant_name"], 5, 10, "s", "")
    inv_svc.add_stock("c1", variants[1]["variant_id"], variants[1]["variant_name"], 3, 20, "s", "")

    summary, detail = svc.stock_explorer("c1")
    tee = summary[summary["product_id"] == product_id].iloc[0]
    assert float(tee["total_available_qty"]) == 8.0
    assert int(tee["variant_count"]) == 2
    assert float(tee["stock_value"]) == 110.0
    assert product_id in detail
    assert not detail[product_id].empty
