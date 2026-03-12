from pathlib import Path

from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, PaymentsRepo, SalesOrderItemsRepo, SalesOrdersRepo, ShipmentsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.domain.models.product import ProductCreate
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService
from easy_ecom.domain.services.sales_service import SalesService


def setup_store(tmp_path: Path):
    store = CsvStore(tmp_path)
    for t, c in TABLE_SCHEMAS.items():
        store.ensure_table(t, c)
    return store


def test_variant_generation_combinations(tmp_path: Path):
    store = setup_store(tmp_path)
    svc = ProductService(ProductsRepo(store), ProductVariantsRepo(store))
    product_id = svc.create(ProductCreate(client_id="c1", supplier="s", product_name="Tee", default_selling_price=100, max_discount_pct=10, sizes_csv="S,M", colors_csv="Red,Blue", others_csv="Cotton"))
    variants = svc.list_variants("c1", product_id)
    assert len(variants) == 4


def test_inventory_stock_by_variant(tmp_path: Path):
    store = setup_store(tmp_path)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    product_svc = ProductService(ProductsRepo(store), ProductVariantsRepo(store))
    product_id = product_svc.create(ProductCreate(client_id="c1", supplier="s", product_name="Tee", default_selling_price=100, max_discount_pct=10, sizes_csv="M", colors_csv="Red", others_csv=""))
    variant_id = product_svc.list_variants("c1", product_id)[0]["variant_id"]
    inv.add_stock("c1", variant_id, "M/Red", 5, 20, "s", "")
    assert inv.available_qty("c1", variant_id) == 5


def test_sales_records_variant_and_deducts_correct_variant_stock(tmp_path: Path):
    store = setup_store(tmp_path)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
    product_svc = ProductService(ProductsRepo(store), ProductVariantsRepo(store))
    sales = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), inv, seq, fin, ProductsRepo(store), variants_repo=ProductVariantsRepo(store))
    product_id = product_svc.create(ProductCreate(client_id="c1", supplier="s", product_name="Tee", default_selling_price=100, max_discount_pct=10, sizes_csv="M", colors_csv="Red", others_csv=""))
    variant_id = product_svc.list_variants("c1", product_id)[0]["variant_id"]
    inv.add_stock("c1", variant_id, "M/Red", 5, 20, "s", "")

    SalesOrdersRepo(store).append({"order_id": "o1", "client_id": "c1", "timestamp": "2025-01-01T00:00:00Z", "customer_id": "cu1", "status": "draft", "subtotal": "0", "discount": "0", "tax": "0", "grand_total": "0", "delivery_cost": "0", "delivery_provider": "", "note": ""})
    SalesOrderItemsRepo(store).append({"order_item_id": "i1", "order_id": "o1", "product_id": variant_id, "prd_description_snapshot": "", "qty": "2", "unit_selling_price": "100", "total_selling_price": "200"})
    sales.confirm_order("o1", {"client_id": "c1", "user_id": "u1"})
    assert inv.available_qty("c1", variant_id) == 3


def test_product_create_generates_default_variant_with_readable_sku(tmp_path: Path):
    store = setup_store(tmp_path)
    svc = ProductService(ProductsRepo(store), ProductVariantsRepo(store))
    pid = svc.create(ProductCreate(client_id="c1", supplier="s", product_name="Premium Tee", default_selling_price=50, max_discount_pct=10, sizes_csv="", colors_csv="", others_csv=""))
    variants = svc.list_variants("c1", pid)
    assert len(variants) == 1
    assert variants[0]["variant_name"] == "Default"
    assert variants[0]["sku_code"].startswith("PREMIU-")
