from __future__ import annotations

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.domain.models.product import ProductCreate
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
                "created_at": now_iso(),
                "is_active": "true",
            }
        )
        return product_id
