from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from easy_ecom.domain.models.product import ProductCreate
from easy_ecom.domain.services.inventory_service import InventoryService
from easy_ecom.domain.services.product_features import parse_features_text
from easy_ecom.domain.services.product_service import ProductService


@dataclass
class VariantWorkspaceEntry:
    size: str = ""
    color: str = ""
    other: str = ""
    qty: float = 0.0
    unit_cost: float = 0.0
    lot_reference: str = ""
    supplier: str = ""
    received_date: str = ""


class CatalogStockService:
    """Application service for the unified Catalog & Stock workspace."""

    def __init__(self, product_service: ProductService, inventory_service: InventoryService):
        self.product_service = product_service
        self.inventory_service = inventory_service

    def search_product_names(self, client_id: str, query: str, limit: int = 12) -> list[str]:
        products = self.product_service.list_by_client(client_id)
        if products.empty:
            return []
        names = products["product_name"].dropna().astype(str)
        if query.strip():
            q = query.strip().lower()
            names = names[names.str.lower().str.contains(q)]
        return names.drop_duplicates().sort_values().head(limit).tolist()

    def load_workspace(self, client_id: str, typed_product_name: str) -> dict[str, object]:
        typed = typed_product_name.strip()
        names = self.search_product_names(client_id, typed, limit=15)
        existing = self.product_service.get_by_name_ci(client_id, typed) if typed else None
        variants = (
            self.product_service.list_variants(client_id, str(existing["product_id"]))
            if existing is not None
            else []
        )
        return {
            "typed_name": typed,
            "suggestions": names,
            "is_existing": existing is not None,
            "product": existing,
            "variants": variants,
        }

    def save_workspace(
        self,
        *,
        client_id: str,
        user_id: str,
        typed_product_name: str,
        supplier: str,
        category: str,
        description: str,
        features_text: str,
        default_selling_price: float,
        max_discount_pct: float,
        variant_entries: list[VariantWorkspaceEntry],
    ) -> tuple[str, list[str], int]:
        product_name = typed_product_name.strip()
        if not product_name:
            raise ValueError("Product name is required")

        product = self.product_service.get_by_name_ci(client_id, product_name)
        if product is None:
            product_id = self.product_service.create(
                ProductCreate(
                    client_id=client_id,
                    supplier=supplier,
                    product_name=product_name,
                    category=category,
                    prd_description=description,
                    prd_features_json=parse_features_text(features_text),
                    default_selling_price=default_selling_price,
                    max_discount_pct=max_discount_pct,
                    sizes_csv="",
                    colors_csv="",
                    others_csv="",
                )
            )
        else:
            product_id = str(product["product_id"])
            self.product_service.update_master(
                client_id=client_id,
                product_id=product_id,
                supplier=supplier,
                product_name=product_name,
                category=category,
                prd_description=description,
                prd_features_json=parse_features_text(features_text),
                default_selling_price=default_selling_price,
                max_discount_pct=max_discount_pct,
            )

        lot_ids: list[str] = []
        updated_variants = 0
        for row in variant_entries:
            if not (row.size.strip() or row.color.strip() or row.other.strip()):
                continue
            variant, _ = self.product_service.upsert_variant(
                client_id=client_id,
                parent_product_id=product_id,
                size=row.size,
                color=row.color,
                other=row.other,
            )
            updated_variants += 1
            if row.qty > 0 and row.unit_cost > 0:
                lot_ids.append(
                    self.inventory_service.add_stock(
                        client_id=client_id,
                        product_id=str(variant["variant_id"]),
                        product_name=str(variant["variant_name"]),
                        qty=float(row.qty),
                        unit_cost=float(row.unit_cost),
                        supplier_snapshot=row.supplier.strip(),
                        note=self._build_stock_note(row.lot_reference, row.received_date),
                        source_type="catalog_stock",
                        source_id=row.lot_reference.strip(),
                        user_id=user_id,
                    )
                )
        return product_id, lot_ids, updated_variants

    @staticmethod
    def _build_stock_note(lot_reference: str, received_date: str) -> str:
        parts = []
        if lot_reference.strip():
            parts.append(f"ref:{lot_reference.strip()}")
        if received_date.strip():
            parts.append(f"received:{received_date.strip()}")
        return " | ".join(parts)

    def stock_explorer(self, client_id: str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
        stock_rows = self.inventory_service.stock_by_lot_with_issues(client_id)
        products = self.product_service.list_by_client(client_id)
        variants = self.product_service.list_variants_by_client(client_id)

        if products.empty:
            return pd.DataFrame(
                columns=[
                    "product_id",
                    "product_name",
                    "total_available_qty",
                    "variant_count",
                    "default_selling_price",
                    "avg_unit_cost",
                    "stock_value",
                ]
            ), {}

        price_cols = products[["product_id", "product_name", "default_selling_price"]].copy()
        price_cols["default_selling_price"] = pd.to_numeric(
            price_cols["default_selling_price"], errors="coerce"
        ).fillna(0.0)

        variant_counts = (
            variants.groupby("parent_product_id", as_index=False)
            .agg(variant_count=("variant_id", "nunique"))
            if not variants.empty
            else pd.DataFrame(columns=["parent_product_id", "variant_count"])
        )

        if stock_rows.empty:
            base = price_cols.copy()
            base["total_available_qty"] = 0.0
            base["variant_count"] = 0
            base["avg_unit_cost"] = 0.0
            base["stock_value"] = 0.0
            return base[
                [
                    "product_id",
                    "product_name",
                    "total_available_qty",
                    "variant_count",
                    "default_selling_price",
                    "avg_unit_cost",
                    "stock_value",
                ]
            ], {}

        stock = stock_rows.copy()
        stock["qty"] = pd.to_numeric(stock["qty"], errors="coerce").fillna(0.0)
        stock["unit_cost"] = pd.to_numeric(stock["unit_cost"], errors="coerce").fillna(0.0)
        stock["line_stock_value"] = stock["qty"] * stock["unit_cost"]

        parent_rollup = stock.groupby(["parent_product_id", "parent_product_name"], as_index=False).agg(
            total_available_qty=("qty", "sum"),
            stock_value=("line_stock_value", "sum"),
        )
        parent_rollup["avg_unit_cost"] = parent_rollup.apply(
            lambda r: float(r["stock_value"] / r["total_available_qty"])
            if float(r["total_available_qty"]) > 0
            else 0.0,
            axis=1,
        )

        summary = price_cols.merge(
            parent_rollup,
            left_on="product_id",
            right_on="parent_product_id",
            how="left",
        ).merge(variant_counts, left_on="product_id", right_on="parent_product_id", how="left")

        for col in ["total_available_qty", "stock_value", "avg_unit_cost", "variant_count"]:
            summary[col] = pd.to_numeric(summary[col], errors="coerce").fillna(0.0)
        summary["variant_count"] = summary["variant_count"].astype(int)
        summary = summary.drop(
            columns=[
                c
                for c in ["parent_product_id_x", "parent_product_id_y", "parent_product_name"]
                if c in summary.columns
            ]
        )
        summary = summary[
            [
                "product_id",
                "product_name",
                "total_available_qty",
                "variant_count",
                "default_selling_price",
                "avg_unit_cost",
                "stock_value",
            ]
        ].sort_values("stock_value", ascending=False)

        detail: dict[str, pd.DataFrame] = {}
        for product_id in summary["product_id"].astype(str).tolist():
            d = stock[stock["parent_product_id"].astype(str) == product_id].copy()
            if d.empty:
                detail[product_id] = pd.DataFrame(
                    columns=["variant_id", "variant_name", "qty", "unit_cost", "stock_value", "lot_id"]
                )
                continue
            d["stock_value"] = d["line_stock_value"]
            detail[product_id] = d[
                ["variant_id", "variant_name", "qty", "unit_cost", "stock_value", "lot_id"]
            ].sort_values(["variant_name", "lot_id"])

        return summary, detail
