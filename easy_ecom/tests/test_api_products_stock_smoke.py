from fastapi.testclient import TestClient
import pandas as pd

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app


class DummyProducts:
    def __init__(self):
        self.products = pd.DataFrame(columns=["product_id", "product_name", "supplier", "category", "prd_description", "prd_features_json", "client_id", "is_active"])
        self.variants = pd.DataFrame(columns=["variant_id", "parent_product_id", "variant_name", "size", "color", "other", "default_selling_price", "max_discount_pct", "client_id", "is_active"])

    def list_by_client(self, client_id: str):
        return self.products[self.products["client_id"] == client_id].copy()

    def list_variants_by_client(self, client_id: str):
        return self.variants[self.variants["client_id"] == client_id].copy()




class DummyReconciliation:
    def normalized_inventory_rows(self, client_id: str):
        return pd.DataFrame(columns=[
            "timestamp", "txn_type", "qty", "txn_id", "inventory_product_id", "inventory_product_name",
            "parent_product_id", "parent_product_name", "inventory_identity_type", "is_unmapped", "variant_id", "unit_cost"
        ])

class DummyInventory:
    def __init__(self):
        self.rows = pd.DataFrame(columns=["product_id", "variant_id", "qty", "unit_cost", "lot_id", "client_id"])
        self.reconciliation = DummyReconciliation()

    def stock_by_lot_with_issues(self, client_id: str):
        return self.rows[self.rows["client_id"] == client_id].copy()


class DummyCatalogStock:
    def __init__(self, products: DummyProducts, inventory: DummyInventory):
        self.products = products
        self.inventory = inventory
        self.next_product = 1
        self.next_variant = 1

    def list_supplier_options(self, client_id: str):
        rows = self.products.list_by_client(client_id)
        return sorted(set(rows["supplier"].tolist()))

    def list_category_options(self, client_id: str):
        rows = self.products.list_by_client(client_id)
        return sorted(set(rows["category"].tolist()))

    def save_workspace(self, **kwargs):
        if "default_selling_price" in kwargs or "max_discount_pct" in kwargs:
            raise AssertionError("Parent pricing fields must not be passed into save_workspace")
        client_id = kwargs["client_id"]
        selected = kwargs.get("selected_product_id", "")
        name = kwargs["typed_product_name"]
        if selected:
            product_id = selected
            self.products.products.loc[self.products.products["product_id"] == product_id, "product_name"] = name
        else:
            product_id = f"p-{self.next_product}"
            self.next_product += 1
            self.products.products = pd.concat([
                self.products.products,
                pd.DataFrame([{
                    "product_id": product_id,
                    "product_name": name,
                    "supplier": kwargs["supplier"],
                    "category": kwargs["category"],
                    "prd_description": kwargs["description"],
                    "prd_features_json": "{}",
                    "client_id": client_id,
                    "is_active": "true",
                }])
            ], ignore_index=True)

        seen = set()
        for idx, row in enumerate(kwargs["variant_entries"], start=1):
            key = f"{row.size.strip().lower()}|{row.color.strip().lower()}|{row.other.strip().lower()}"
            if key == '||':
                raise ValueError(f"Variant row {idx} must include at least one identity field (size/color/other)")
            if key in seen:
                raise ValueError("Duplicate variant identity in request: each size/color/other combination must be unique")
            seen.add(key)

            scoped = self.products.variants[
                (self.products.variants["client_id"] == client_id)
                & (self.products.variants["parent_product_id"] == product_id)
            ]
            candidate_id = str(getattr(row, "variant_id", "") or "").strip()
            by_id = scoped[scoped["variant_id"].astype(str) == candidate_id] if candidate_id else pd.DataFrame()
            if not by_id.empty:
                variant_id = str(by_id.iloc[0]["variant_id"])
                self.products.variants.loc[by_id.index, ["size", "color", "other", "default_selling_price", "max_discount_pct"]] = [
                    row.size,
                    row.color,
                    row.other,
                    str(row.default_selling_price),
                    str(row.max_discount_pct),
                ]
            else:
                existing = scoped[
                    (scoped["size"].astype(str).str.lower() == row.size.lower())
                    & (scoped["color"].astype(str).str.lower() == row.color.lower())
                    & (scoped["other"].astype(str).str.lower() == row.other.lower())
                ]
                if existing.empty:
                    variant_id = f"v-{self.next_variant}"
                    self.next_variant += 1
                    self.products.variants = pd.concat([
                        self.products.variants,
                        pd.DataFrame([{
                            "variant_id": variant_id,
                            "parent_product_id": product_id,
                            "variant_name": f"{name} | {row.size}/{row.color}/{row.other}",
                            "size": row.size,
                            "color": row.color,
                            "other": row.other,
                            "default_selling_price": str(row.default_selling_price),
                            "max_discount_pct": str(row.max_discount_pct),
                            "client_id": client_id,
                            "is_active": "true",
                        }])
                    ], ignore_index=True)
                else:
                    variant_id = str(existing.iloc[0]["variant_id"])

            if row.qty > 0:
                self.inventory.rows = pd.concat([
                    self.inventory.rows,
                    pd.DataFrame([{"product_id": product_id, "variant_id": variant_id, "qty": row.qty, "unit_cost": row.unit_cost, "lot_id": f"lot-{len(self.inventory.rows)+1}", "client_id": client_id}])
                ], ignore_index=True)

        return product_id, [], len(kwargs["variant_entries"])


class DummyContainer:
    def __init__(self):
        self.products = DummyProducts()
        self.inventory = DummyInventory()
        self.catalog_stock = DummyCatalogStock(self.products, self.inventory)


def _client(container: DummyContainer):
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id="u-test", client_id="c-test", roles=["SUPER_ADMIN"])
    return TestClient(app)


def test_create_and_reload_two_variants_and_stock_by_variant_id_only():
    container = DummyContainer()
    client = _client(container)

    response = client.post('/products-stock/save', json={
        "mode": "new",
        "identity": {"productName": "Shirt", "supplier": "Nova", "category": "Apparel", "description": "", "features": []},
        "variants": [
            {"id": "", "size": "S", "color": "Black", "other": "", "qty": 2, "cost": 10, "defaultSellingPrice": 20, "maxDiscountPct": 10},
            {"id": "", "size": "M", "color": "Black", "other": "", "qty": 3, "cost": 11, "defaultSellingPrice": 21, "maxDiscountPct": 10},
        ],
    })
    assert response.status_code == 200

    snapshot = client.get('/products-stock/snapshot')
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert len(body['products']) == 1
    assert len(body['products'][0]['variants']) == 2
    assert all(row['variant_id'] if 'variant_id' in row else True for row in container.inventory.rows.to_dict(orient='records'))

    app.dependency_overrides.clear()


def test_duplicate_identity_rejected():
    container = DummyContainer()
    client = _client(container)
    response = client.post('/products-stock/save', json={
        "mode": "new",
        "identity": {"productName": "Shirt", "supplier": "Nova", "category": "Apparel", "description": "", "features": []},
        "variants": [
            {"id": "", "size": "S", "color": "Black", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 20, "maxDiscountPct": 10},
            {"id": "", "size": "S", "color": "Black", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 20, "maxDiscountPct": 10},
        ],
    })
    assert response.status_code == 422 or response.status_code == 400
    app.dependency_overrides.clear()


def test_blank_identity_rejected():
    container = DummyContainer()
    client = _client(container)
    response = client.post('/products-stock/save', json={
        "mode": "new",
        "identity": {"productName": "Shirt", "supplier": "Nova", "category": "Apparel", "description": "", "features": []},
        "variants": [{"id": "", "size": "", "color": "", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 20, "maxDiscountPct": 10}],
    })
    assert response.status_code == 422 or response.status_code == 400
    app.dependency_overrides.clear()



def test_inventory_save_contract_persists_new_and_existing_variants_without_parent_price_dependency():
    container = DummyContainer()
    client = _client(container)

    create = client.post('/products-stock/save', json={
        "mode": "new",
        "identity": {"productName": "Combo Tee", "supplier": "Nova", "category": "Apparel", "description": "", "features": []},
        "variants": [
            {"id": "", "size": "S", "color": "Red", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 20, "maxDiscountPct": 10},
            {"id": "", "size": "S", "color": "Blue", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 20, "maxDiscountPct": 10},
            {"id": "", "size": "M", "color": "Red", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 22, "maxDiscountPct": 12},
            {"id": "", "size": "M", "color": "Blue", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 22, "maxDiscountPct": 12},
        ],
    })
    assert create.status_code == 200

    first_snapshot = client.get('/products-stock/snapshot')
    assert first_snapshot.status_code == 200
    first_body = first_snapshot.json()
    assert len(first_body["products"]) == 1
    assert len(first_body["products"][0]["variants"]) == 4

    product_id = first_body["products"][0]["id"]
    update = client.post('/products-stock/save', json={
        "mode": "existing",
        "selectedProductId": product_id,
        "identity": {"productName": "Combo Tee", "supplier": "Nova", "category": "Apparel", "description": "", "features": []},
        "variants": [
            {"id": "", "size": "S", "color": "Red", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 20, "maxDiscountPct": 10},
            {"id": "", "size": "S", "color": "Blue", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 20, "maxDiscountPct": 10},
            {"id": "", "size": "M", "color": "Red", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 22, "maxDiscountPct": 12},
            {"id": "", "size": "M", "color": "Blue", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 22, "maxDiscountPct": 12},
            {"id": "", "size": "L", "color": "Black", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 24, "maxDiscountPct": 15},
        ],
    })
    assert update.status_code == 200

    second_snapshot = client.get('/products-stock/snapshot')
    assert second_snapshot.status_code == 200
    second_body = second_snapshot.json()
    assert len(second_body["products"]) == 1
    assert len(second_body["products"][0]["variants"]) == 5
    keys = {(row["size"], row["color"], row["other"]) for row in second_body["products"][0]["variants"]}
    assert ("L", "Black", "") in keys

    app.dependency_overrides.clear()

def test_existing_product_update_path_uses_selected_product_id():
    container = DummyContainer()
    client = _client(container)
    first = client.post('/products-stock/save', json={
        "mode": "new",
        "identity": {"productName": "Shirt", "supplier": "Nova", "category": "Apparel", "description": "", "features": []},
        "variants": [{"id": "", "size": "S", "color": "Black", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 20, "maxDiscountPct": 10}],
    })
    assert first.status_code == 200
    product_id = container.products.products.iloc[0]["product_id"]

    update = client.post('/products-stock/save', json={
        "mode": "existing",
        "selectedProductId": product_id,
        "identity": {"productName": "Shirt Updated", "supplier": "Nova", "category": "Apparel", "description": "", "features": []},
        "variants": [{"id": "", "size": "S", "color": "Black", "other": "", "qty": 0, "cost": 0, "defaultSellingPrice": 20, "maxDiscountPct": 10}],
    })
    assert update.status_code == 200
    assert container.products.products.iloc[0]["product_name"] == "Shirt Updated"
    app.dependency_overrides.clear()


def test_existing_variant_id_update_and_new_variant_create_keep_snapshot_inventory_stable():
    container = DummyContainer()
    client = _client(container)

    create = client.post('/products-stock/save', json={
        "mode": "new",
        "identity": {"productName": "Hoodie", "supplier": "Nova", "category": "Apparel", "description": "", "features": []},
        "variants": [
            {"id": "", "size": "M", "color": "Black", "other": "", "qty": 2, "cost": 10, "defaultSellingPrice": 30, "maxDiscountPct": 10},
        ],
    })
    assert create.status_code == 200

    snap1 = client.get('/products-stock/snapshot')
    assert snap1.status_code == 200
    body1 = snap1.json()
    product_id = body1['products'][0]['id']
    existing_variant_id = body1['products'][0]['variants'][0]['id']

    update = client.post('/products-stock/save', json={
        "mode": "existing",
        "selectedProductId": product_id,
        "identity": {"productName": "Hoodie", "supplier": "Nova", "category": "Apparel", "description": "", "features": []},
        "variants": [
            {"id": existing_variant_id, "size": "M", "color": "Black", "other": "", "qty": 0, "cost": 11, "defaultSellingPrice": 32, "maxDiscountPct": 12},
            {"id": "", "size": "L", "color": "Black", "other": "", "qty": 1, "cost": 12, "defaultSellingPrice": 34, "maxDiscountPct": 12},
        ],
    })
    assert update.status_code == 200
    assert update.json() == {"success": True}

    snap2 = client.get('/products-stock/snapshot')
    assert snap2.status_code == 200
    body2 = snap2.json()
    assert len(body2['products']) == 1
    variants = body2['products'][0]['variants']
    assert len(variants) == 2
    ids = {row['id'] for row in variants}
    assert existing_variant_id in ids

    inventory = client.get('/inventory')
    assert inventory.status_code == 200
    inv_body = inventory.json()
    inv_ids = {item['item_id'] for item in inv_body['items']}
    assert existing_variant_id in inv_ids
    assert len(inv_ids) == 2

    app.dependency_overrides.clear()
