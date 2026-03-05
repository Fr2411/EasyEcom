from __future__ import annotations

import itertools

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.domain.models.product import ProductCreate, ProductPricingUpdate


class ProductService:
    def __init__(self, repo: ProductsRepo, variants_repo: ProductVariantsRepo | None = None):
        self.repo = repo
        self.variants_repo = variants_repo

    @staticmethod
    def normalize_options(csv_values: str) -> list[str]:
        seen: set[str] = set()
        values: list[str] = []
        for raw in str(csv_values or "").split(","):
            value = raw.strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(value.title())
        return values

    def _variant_name(self, size: str, color: str, other: str) -> str:
        parts = []
        if size:
            parts.append(f"Size:{size}")
        if color:
            parts.append(f"Color:{color}")
        if other:
            parts.append(f"Other:{other}")
        return " | ".join(parts) if parts else "Default"

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
                "is_parent": "true",
                "sizes_csv": payload.sizes_csv,
                "colors_csv": payload.colors_csv,
                "others_csv": payload.others_csv,
                "parent_product_id": "",
            }
        )
        if self.variants_repo is not None:
            self.generate_variants(payload.client_id, product_id, payload.sizes_csv, payload.colors_csv, payload.others_csv)
        return product_id

    def list_by_client(self, client_id: str):
        df = self.repo.all()
        if df.empty:
            return df
        return df[df["client_id"] == client_id].copy()

    def list_variants(self, client_id: str, parent_product_id: str):
        if self.variants_repo is None:
            return []
        d = self.variants_repo.all()
        if d.empty:
            return []
        scoped = d[(d["client_id"] == client_id) & (d["parent_product_id"] == parent_product_id) & (d["is_active"].astype(str).str.lower() == "true")].copy()
        return scoped.sort_values("variant_name").to_dict(orient="records")

    def generate_variants(self, client_id: str, parent_product_id: str, sizes_csv: str, colors_csv: str, others_csv: str) -> list[dict[str, str]]:
        if self.variants_repo is None:
            return []
        products = self.list_by_client(client_id)
        parent = products[products["product_id"] == parent_product_id]
        if parent.empty:
            raise ValueError("Parent product not found")
        row = parent.iloc[0]
        sizes = self.normalize_options(sizes_csv) or [""]
        colors = self.normalize_options(colors_csv) or [""]
        others = self.normalize_options(others_csv) or [""]

        all_rows = self.variants_repo.all()
        existing_keys: set[str] = set()
        if not all_rows.empty:
            scoped = all_rows[(all_rows["client_id"] == client_id) & (all_rows["parent_product_id"] == parent_product_id)]
            existing_keys = set((scoped["size"] + "|" + scoped["color"] + "|" + scoped["other"]).tolist())

        created: list[dict[str, str]] = []
        for size, color, other in itertools.product(sizes, colors, others):
            key = f"{size}|{color}|{other}"
            if key in existing_keys:
                continue
            variant_id = new_uuid()
            variant_name = self._variant_name(size, color, other)
            sku_code = f"{parent_product_id[:8]}-{variant_name.replace(' ', '').replace('|', '-').replace(':', '-')[:30]}"
            record = {
                "variant_id": variant_id,
                "client_id": client_id,
                "parent_product_id": parent_product_id,
                "variant_name": variant_name,
                "size": size,
                "color": color,
                "other": other,
                "sku_code": sku_code,
                "default_selling_price": str(row.get("default_selling_price", "0")),
                "max_discount_pct": str(row.get("max_discount_pct", "0")),
                "is_active": "true",
                "created_at": now_iso(),
            }
            self.variants_repo.append(record)
            created.append(record)
        return created

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
