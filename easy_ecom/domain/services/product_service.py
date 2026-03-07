from __future__ import annotations

import itertools

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.repos.base import TabularRepo
from easy_ecom.domain.models.product import ProductCreate, ProductPricingUpdate


class ProductService:
    def __init__(self, repo: TabularRepo, variants_repo: TabularRepo | None = None):
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
        dup = df[
            (df["client_id"] == payload.client_id)
            & (df["product_name"].str.lower() == payload.product_name.lower())
        ]
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
            self.generate_variants(
                payload.client_id,
                product_id,
                payload.sizes_csv,
                payload.colors_csv,
                payload.others_csv,
            )
        return product_id

    def list_by_client(self, client_id: str):
        df = self.repo.all()
        if df.empty:
            return df
        return df[df["client_id"] == client_id].copy()

    def get_by_id(self, client_id: str, product_id: str) -> dict[str, str] | None:
        product_id = str(product_id or "").strip()
        if not product_id:
            return None
        df = self.list_by_client(client_id)
        if df.empty:
            return None
        match = df[df["product_id"].astype(str) == product_id]
        if match.empty:
            return None
        return match.iloc[0].to_dict()

    def list_variants(self, client_id: str, parent_product_id: str):
        if self.variants_repo is None:
            return []
        d = self.variants_repo.all()
        if d.empty:
            return []
        scoped = d[
            (d["client_id"] == client_id)
            & (d["parent_product_id"] == parent_product_id)
            & (d["is_active"].astype(str).str.lower() == "true")
        ].copy()
        return scoped.sort_values("variant_name").to_dict(orient="records")

    def generate_variants(
        self,
        client_id: str,
        parent_product_id: str,
        sizes_csv: str,
        colors_csv: str,
        others_csv: str,
    ) -> list[dict[str, str]]:
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
            scoped = all_rows[
                (all_rows["client_id"] == client_id)
                & (all_rows["parent_product_id"] == parent_product_id)
            ]
            existing_keys = set(
                (scoped["size"] + "|" + scoped["color"] + "|" + scoped["other"]).tolist()
            )

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

    def get_by_name_ci(self, client_id: str, product_name: str) -> dict[str, str] | None:
        product_name = product_name.strip()
        if not product_name:
            return None
        df = self.list_by_client(client_id)
        if df.empty:
            return None
        names = df["product_name"].fillna("").astype(str)
        match = df[names.str.lower() == product_name.lower()]
        if match.empty:
            return None
        return match.iloc[0].to_dict()

    def list_variants_by_client(self, client_id: str):
        if self.variants_repo is None:
            return self.repo.all().head(0).iloc[0:0]
        d = self.variants_repo.all()
        if d.empty:
            return d
        scoped = d[
            (d["client_id"] == client_id) & (d["is_active"].astype(str).str.lower() == "true")
        ]
        return scoped.copy()

    def update_master(
        self,
        *,
        client_id: str,
        product_id: str,
        supplier: str,
        product_name: str,
        category: str,
        prd_description: str,
        prd_features_json: str,
        default_selling_price: float,
        max_discount_pct: float,
    ) -> None:
        products = self.repo.all()
        idx = products[
            (products["client_id"] == client_id) & (products["product_id"] == product_id)
        ].index
        if len(idx) == 0:
            raise ValueError("Product not found for this client")
        dup = products[
            (products["client_id"] == client_id)
            & (products["product_id"] != product_id)
            & (
                products["product_name"].fillna("").astype(str).str.lower()
                == product_name.strip().lower()
            )
        ]
        if not dup.empty:
            raise ValueError("Duplicate product name for this client")
        i = idx[0]
        products.loc[i, "supplier"] = supplier
        products.loc[i, "product_name"] = product_name.strip()
        products.loc[i, "category"] = category
        products.loc[i, "prd_description"] = prd_description
        products.loc[i, "prd_features_json"] = prd_features_json
        products.loc[i, "default_selling_price"] = str(default_selling_price)
        products.loc[i, "max_discount_pct"] = str(max_discount_pct)
        self.repo.save(products)

    def upsert_variant(
        self,
        *,
        client_id: str,
        parent_product_id: str,
        size: str,
        color: str,
        other: str,
        default_selling_price: float | None = None,
        max_discount_pct: float | None = None,
    ) -> tuple[dict[str, str], bool]:
        if self.variants_repo is None:
            raise ValueError("Variant repository not configured")
        size = size.strip().title()
        color = color.strip().title()
        other = other.strip().title()
        variants = self.variants_repo.all()
        if not variants.empty:
            scoped = variants[
                (variants["client_id"] == client_id)
                & (variants["parent_product_id"] == parent_product_id)
                & (variants["size"].fillna("").astype(str).str.lower() == size.lower())
                & (variants["color"].fillna("").astype(str).str.lower() == color.lower())
                & (variants["other"].fillna("").astype(str).str.lower() == other.lower())
            ]
            if not scoped.empty:
                row = scoped.iloc[0].to_dict()
                if default_selling_price is not None or max_discount_pct is not None:
                    i = scoped.index[0]
                    if default_selling_price is not None:
                        variants.loc[i, "default_selling_price"] = str(default_selling_price)
                        row["default_selling_price"] = str(default_selling_price)
                    if max_discount_pct is not None:
                        variants.loc[i, "max_discount_pct"] = str(max_discount_pct)
                        row["max_discount_pct"] = str(max_discount_pct)
                    self.variants_repo.save(variants)
                return row, False

        products = self.list_by_client(client_id)
        parent = products[products["product_id"] == parent_product_id]
        if parent.empty:
            raise ValueError("Parent product not found")
        product = parent.iloc[0]
        variant_name = self._variant_name(size, color, other)
        variant_id = new_uuid()
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
            "default_selling_price": str(
                default_selling_price
                if default_selling_price is not None
                else product.get("default_selling_price", "0")
            ),
            "max_discount_pct": str(
                max_discount_pct
                if max_discount_pct is not None
                else product.get("max_discount_pct", "0")
            ),
            "is_active": "true",
            "created_at": now_iso(),
        }
        self.variants_repo.append(record)
        return record, True

    def update_pricing(
        self, client_id: str, product_id: str, payload: ProductPricingUpdate
    ) -> None:
        products = self.repo.all()
        idx = products[
            (products["client_id"] == client_id) & (products["product_id"] == product_id)
        ].index
        if len(idx) == 0:
            raise ValueError("Product not found for this client")
        i = idx[0]
        products.loc[i, "default_selling_price"] = str(payload.default_selling_price)
        products.loc[i, "max_discount_pct"] = str(payload.max_discount_pct)
        self.repo.save(products)
