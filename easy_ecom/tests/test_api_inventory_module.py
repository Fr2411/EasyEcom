from pathlib import Path

from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService


class InventoryContainer:
    def __init__(self, tmp_path: Path) -> None:
        store = CsvStore(tmp_path)
        for table, columns in TABLE_SCHEMAS.items():
            store.ensure_table(table, columns)

        products_repo = ProductsRepo(store)
        variants_repo = ProductVariantsRepo(store)
        inventory_repo = InventoryTxnRepo(store)
        self.products = ProductService(products_repo, variants_repo)
        self.inventory = InventoryService(
            inventory_repo,
            SequenceService(SequencesRepo(store)),
            products_repo=products_repo,
            variants_repo=variants_repo,
        )

        products_repo.append(
            {
                "product_id": "p-tenant-a",
                "client_id": "tenant-a",
                "supplier": "sup",
                "product_name": "Tee",
                "category": "Apparel",
                "prd_description": "",
                "prd_features_json": "{}",
                "default_selling_price": "10",
                "max_discount_pct": "5",
                "created_at": "",
                "is_active": "true",
                "is_parent": "true",
                "sizes_csv": "",
                "colors_csv": "",
                "others_csv": "",
                "parent_product_id": "",
            }
        )
        variants_repo.append(
            {
                "variant_id": "v-tenant-a",
                "client_id": "tenant-a",
                "parent_product_id": "p-tenant-a",
                "variant_name": "Size:M",
                "size": "M",
                "color": "",
                "other": "",
                "sku_code": "SKU-M",
                "default_selling_price": "12",
                "max_discount_pct": "5",
                "is_active": "true",
                "created_at": "",
            }
        )
        products_repo.append(
            {
                "product_id": "p-tenant-b",
                "client_id": "tenant-b",
                "supplier": "sup",
                "product_name": "Other",
                "category": "Apparel",
                "prd_description": "",
                "prd_features_json": "{}",
                "default_selling_price": "10",
                "max_discount_pct": "5",
                "created_at": "",
                "is_active": "true",
                "is_parent": "true",
                "sizes_csv": "",
                "colors_csv": "",
                "others_csv": "",
                "parent_product_id": "",
            }
        )

        self.inventory.add_stock("tenant-a", "v-tenant-a", "Size:M", 10, 2, "", "seed", user_id="u-a")
        self.inventory.add_stock("tenant-b", "p-tenant-b", "Other", 7, 3, "", "seed", user_id="u-b")
        self.inventory.repo.append(
            {
                "txn_id": "sale-out-1",
                "client_id": "tenant-a",
                "timestamp": "2026-01-01T00:00:00Z",
                "user_id": "u-a",
                "txn_type": "OUT",
                "product_id": "v-tenant-a",
                "product_name": "Size:M",
                "qty": "2",
                "unit_cost": "0",
                "total_cost": "0",
                "supplier_snapshot": "",
                "note": "sale",
                "source_type": "sale",
                "source_id": "sale-1",
                "lot_id": "",
            }
        )


def test_inventory_requires_auth(tmp_path: Path) -> None:
    client = TestClient(create_app())
    assert client.get('/inventory').status_code == 401
    assert client.get('/inventory/movements').status_code == 401
    assert client.post('/inventory/adjustments', json={"item_id": "x", "adjustment_type": "stock_in", "quantity": 1, "unit_cost": 1}).status_code == 401


def test_inventory_list_movements_and_adjustments(tmp_path: Path) -> None:
    container = InventoryContainer(tmp_path)
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u-a', client_id='tenant-a', roles=['SUPER_ADMIN'])
    client = TestClient(app)

    inv_res = client.get('/inventory')
    assert inv_res.status_code == 200
    assert len(inv_res.json()['items']) == 1
    assert inv_res.json()['items'][0]['item_id'] == 'v-tenant-a'

    movements_res = client.get('/inventory/movements', params={"item_id": "v-tenant-a"})
    assert movements_res.status_code == 200
    movement_sources = {row['source_type'] for row in movements_res.json()['items']}
    assert 'sale' in movement_sources

    adjust_in = client.post('/inventory/adjustments', json={
        "item_id": "v-tenant-a",
        "adjustment_type": "stock_in",
        "quantity": 3,
        "unit_cost": 2,
        "reason": "purchase receive",
        "note": "manual",
        "reference": "recv-1",
    })
    assert adjust_in.status_code == 201

    adjust_out = client.post('/inventory/adjustments', json={
        "item_id": "v-tenant-a",
        "adjustment_type": "stock_out",
        "quantity": 2,
        "reason": "manual issue",
        "note": "manual",
        "reference": "iss-1",
    })
    assert adjust_out.status_code == 201

    detail_res = client.get('/inventory/v-tenant-a')
    assert detail_res.status_code == 200
    assert detail_res.json()['item']['available_qty'] == 11.0

    bad_payload = client.post('/inventory/adjustments', json={"item_id": "v-tenant-a", "adjustment_type": "correction", "quantity_delta": 0})
    assert bad_payload.status_code == 422

    cross_tenant = client.post('/inventory/adjustments', json={"item_id": "p-tenant-b", "adjustment_type": "stock_in", "quantity": 1, "unit_cost": 1})
    assert cross_tenant.status_code == 404

    app.dependency_overrides.clear()
