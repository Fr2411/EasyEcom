from __future__ import annotations

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.domain.models.product import ProductCreate, ProductPricingUpdate
from easy_ecom.data.repos.csv.products_repo import ProductsRepo


class ProductService:
    def __init__(self, repo: ProductsRepo):
        self.repo = repo

    def create(self, payload: ProductCreate) -> str:
        df = self.repo.all()
        dup = df[(df["client_id"] == payload.client_id) & (df["product_name"].str.lower() == payload.product_name.lower())]
        if not dup.empty:
            raise ValueError("Duplicate product name for this client")
        product_id = new_uuid()
        self.repo.append(
            {
                "product_id": product_id,
                "client_id": payload.client_id,
                "supplier": payload.supplier,
                "product_name": payload.product_name,
                "category": payload.category,
                "prd_description": payload.prd_description,
                "prd_features_json": payload.prd_features_json,
                "default_selling_price": str(payload.default_selling_price),
                "max_discount_pct": str(payload.max_discount_pct),
                "created_at": now_iso(),
                "is_active": "true",
            }
        )
        return product_id

    def list_by_client(self, client_id: str):
        df = self.repo.all()
        if df.empty:
            return df
        return df[df["client_id"] == client_id].copy()

    def get_by_name(self, client_id: str, product_name: str) -> dict[str, str] | None:
        df = self.list_by_client(client_id)
        match = df[df["product_name"] == product_name]
        if match.empty:
            return None
        return match.iloc[0].to_dict()

    def update_pricing(self, client_id: str, product_id: str, payload: ProductPricingUpdate) -> None:
        products = self.repo.all()
        idx = products[(products["client_id"] == client_id) & (products["product_id"] == product_id)].index
        if len(idx) == 0:
            raise ValueError("Product not found for this client")
        i = idx[0]
        products.loc[i, "default_selling_price"] = str(payload.default_selling_price)
        products.loc[i, "max_discount_pct"] = str(payload.max_discount_pct)
        self.repo.save(products)
