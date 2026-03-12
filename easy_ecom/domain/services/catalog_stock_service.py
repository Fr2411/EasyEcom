from __future__ import annotations

import json
import itertools
import logging
from dataclasses import dataclass

import pandas as pd

from easy_ecom.domain.models.product import ProductCreate
from easy_ecom.domain.services.inventory_service import InventoryService
from easy_ecom.domain.services.product_features import parse_features_text
from easy_ecom.domain.services.product_service import ProductService


logger = logging.getLogger(__name__)


@dataclass
class VariantWorkspaceEntry:
    variant_id: str = ""
    variant_label: str = ""
    size: str = ""
    color: str = ""
    other: str = ""
    qty: float = 0.0
    unit_cost: float = 0.0
    default_selling_price: float = 0.0
    max_discount_pct: float = 10.0
    lot_reference: str = ""
    supplier: str = ""
    received_date: str = ""

    def identity_key(self) -> str:
        return "|".join(
            str(value or "").strip().lower() for value in (self.size, self.color, self.other)
        )

    def has_identity(self) -> bool:
        return any(str(value or "").strip() for value in (self.size, self.color, self.other))


class CatalogStockService:
    """Application service for the unified Catalog & Stock workspace."""

    def __init__(self, product_service: ProductService, inventory_service: InventoryService):
        self.product_service = product_service
        self.inventory_service = inventory_service

    def suggest_products(self, client_id: str, query: str, limit: int = 15) -> list[dict[str, str]]:
        products = self.product_service.list_by_client(client_id)
        if products.empty:
            return []
        scoped = products[["product_id", "product_name"]].copy()
        scoped["product_name"] = scoped["product_name"].fillna("").astype(str)
        if query.strip():
            q = query.strip().lower()
            scoped = scoped[scoped["product_name"].str.lower().str.contains(q)]
        scoped = scoped.sort_values("product_name").drop_duplicates(
            subset=["product_name"], keep="first"
        )
        return scoped.head(limit).to_dict(orient="records")

    def list_supplier_options(self, client_id: str) -> list[str]:
        products = self.product_service.list_by_client(client_id)
        if products.empty or "supplier" not in products.columns:
            return []
        suppliers = products["supplier"].fillna("").astype(str).str.strip()
        suppliers = suppliers[suppliers != ""]
        return sorted(suppliers.drop_duplicates().tolist())

    def list_category_options(self, client_id: str) -> list[str]:
        products = self.product_service.list_by_client(client_id)
        if products.empty or "category" not in products.columns:
            return ["General"]
        categories = products["category"].fillna("").astype(str).str.strip()
        categories = categories[categories != ""]
        values = sorted(categories.drop_duplicates().tolist())
        return values or ["General"]

    def load_workspace(
        self, client_id: str, typed_product_name: str, selected_product_id: str = ""
    ) -> dict[str, object]:
        typed = typed_product_name.strip()
        existing = None
        if selected_product_id.strip():
            existing = self.product_service.get_by_id(client_id, selected_product_id.strip())
        elif typed:
            existing = self.product_service.get_by_name_ci(client_id, typed)

        variants = (
            self.product_service.list_variants(client_id, str(existing["product_id"]))
            if existing
            else []
        )
        return {
            "typed_name": typed,
            "is_existing": existing is not None,
            "product": existing,
            "variants": variants,
            "supplier_options": self.list_supplier_options(client_id),
            "category_options": self.list_category_options(client_id),
        }

    @staticmethod
    def features_to_text(raw_json: str) -> str:
        if not str(raw_json or "").strip() or str(raw_json).strip() == "{}":
            return ""
        try:
            parsed = json.loads(raw_json)
            values = parsed.get("features", []) if isinstance(parsed, dict) else []
            if isinstance(values, list):
                return ", ".join([str(v) for v in values if str(v).strip()])
        except Exception:
            return str(raw_json)
        return ""

    def generate_variant_rows(
        self,
        *,
        sizes_csv: str,
        colors_csv: str,
        others_csv: str,
        default_selling_price: float,
        max_discount_pct: float,
    ) -> list[VariantWorkspaceEntry]:
        sizes = self.product_service.normalize_options(sizes_csv) or [""]
        colors = self.product_service.normalize_options(colors_csv) or [""]
        others = self.product_service.normalize_options(others_csv) or [""]

        rows: list[VariantWorkspaceEntry] = []
        for size, color, other in itertools.product(sizes, colors, others):
            rows.append(
                VariantWorkspaceEntry(
                    variant_label=self.product_service._variant_name("", size, color, other),
                    size=size,
                    color=color,
                    other=other,
                    default_selling_price=float(default_selling_price),
                    max_discount_pct=float(max_discount_pct),
                ),
            )
        return rows

    @staticmethod
    def apply_shared_cost(
        rows: list[VariantWorkspaceEntry], shared_cost: float
    ) -> list[VariantWorkspaceEntry]:
        for row in rows:
            if float(row.unit_cost) <= 0:
                row.unit_cost = float(shared_cost)
        return rows

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
        selected_product_id: str = "",
    ) -> tuple[str, list[str], int]:
        product_name = typed_product_name.strip()
        if not product_name:
            raise ValueError("Product name is required")
        if not variant_entries:
            raise ValueError("At least one variant is required")

        normalized_entries: list[VariantWorkspaceEntry] = []
        seen: set[str] = set()
        for index, entry in enumerate(variant_entries, start=1):
            row = VariantWorkspaceEntry(
                variant_id=str(entry.variant_id or "").strip(),
                variant_label=str(entry.variant_label or "").strip(),
                size=str(entry.size or "").strip().title(),
                color=str(entry.color or "").strip().title(),
                other=str(entry.other or "").strip().title(),
                qty=float(entry.qty or 0),
                unit_cost=float(entry.unit_cost or 0),
                default_selling_price=float(entry.default_selling_price or 0),
                max_discount_pct=float(entry.max_discount_pct or 0),
                lot_reference=str(entry.lot_reference or "").strip(),
                supplier=str(entry.supplier or "").strip(),
                received_date=str(entry.received_date or "").strip(),
            )
            if not row.has_identity():
                raise ValueError(f"Variant row {index} must include at least one identity field (size/color/other)")
            key = row.identity_key()
            if key in seen:
                raise ValueError("Duplicate variant identity in request: each size/color/other combination must be unique")
            seen.add(key)
            normalized_entries.append(row)

        product = (
            self.product_service.get_by_id(client_id, selected_product_id)
            if selected_product_id.strip()
            else None
        )
        if product is None:
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
                    default_selling_price=0,
                    max_discount_pct=0,
                    sizes_csv="",
                    colors_csv="",
                    others_csv="",
                ),
                generate_variants_on_create=False,
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
                default_selling_price=0,
                max_discount_pct=0,
            )

        variants_df = self.product_service.variants_repo.all() if self.product_service.variants_repo is not None else pd.DataFrame()
        scoped = variants_df[
            (variants_df["client_id"] == client_id)
            & (variants_df["parent_product_id"] == product_id)
        ].copy() if not variants_df.empty else pd.DataFrame()

        existing_by_identity = {
            "|".join([
                str(r.get("size", "")).strip().lower(),
                str(r.get("color", "")).strip().lower(),
                str(r.get("other", "")).strip().lower(),
            ]): r
            for _, r in scoped.iterrows()
        }

        lot_ids: list[str] = []
        upserts = 0
        for row in normalized_entries:
            existing = existing_by_identity.get(row.identity_key())
            if existing is not None:
                variant_id = str(existing.get("variant_id", ""))
                mask = variants_df["variant_id"].astype(str) == variant_id
                variants_df.loc[mask, "variant_name"] = self.product_service._variant_name(product_name, row.size, row.color, row.other)
                variants_df.loc[mask, "size"] = row.size
                variants_df.loc[mask, "color"] = row.color
                variants_df.loc[mask, "other"] = row.other
                variants_df.loc[mask, "default_selling_price"] = str(row.default_selling_price)
                variants_df.loc[mask, "max_discount_pct"] = str(row.max_discount_pct)
            else:
                created, _ = self.product_service.upsert_variant(
                    client_id=client_id,
                    parent_product_id=product_id,
                    variant_id="",
                    size=row.size,
                    color=row.color,
                    other=row.other,
                    default_selling_price=row.default_selling_price,
                    max_discount_pct=row.max_discount_pct,
                )
                variant_id = str(created.get("variant_id", "")).strip()
                if not variant_id:
                    raise ValueError("Failed to persist variant identity")
            if row.qty > 0:
                if row.unit_cost <= 0:
                    raise ValueError("Stock rows with quantity must include a positive unit cost")
                lot_ids.append(
                    self.inventory_service.add_stock(
                        client_id=client_id,
                        product_id=product_id,
                        variant_id=variant_id,
                        product_name=self.product_service._variant_name(product_name, row.size, row.color, row.other),
                        qty=row.qty,
                        unit_cost=row.unit_cost,
                        supplier_snapshot=row.supplier,
                        note=self._build_stock_note(row.lot_reference, row.received_date),
                        source_type="catalog_stock",
                        source_id=row.lot_reference,
                        user_id=user_id,
                    )
                )
            upserts += 1

        if self.product_service.variants_repo is not None and not variants_df.empty:
            self.product_service.variants_repo.save(variants_df)
        return product_id, lot_ids, upserts

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
            return (
                pd.DataFrame(
                    columns=[
                        "product_id",
                        "product_name",
                        "total_available_qty",
                        "variant_count",
                        "default_selling_price",
                        "avg_unit_cost",
                        "stock_value",
                    ]
                ),
                {},
            )

        price_cols = products[["product_id", "product_name", "default_selling_price"]].copy()
        price_cols["default_selling_price"] = pd.to_numeric(
            price_cols["default_selling_price"], errors="coerce"
        ).fillna(0.0)

        variant_counts = (
            variants.groupby("parent_product_id", as_index=False).agg(
                variant_count=("variant_id", "nunique")
            )
            if not variants.empty
            else pd.DataFrame(columns=["parent_product_id", "variant_count"])
        )

        if stock_rows.empty:
            base = price_cols.copy()
            base["total_available_qty"] = 0.0
            base["variant_count"] = 0
            base["avg_unit_cost"] = 0.0
            base["stock_value"] = 0.0
            return (
                base[
                    [
                        "product_id",
                        "product_name",
                        "total_available_qty",
                        "variant_count",
                        "default_selling_price",
                        "avg_unit_cost",
                        "stock_value",
                    ]
                ],
                {},
            )

        stock = stock_rows.copy()
        stock["qty"] = pd.to_numeric(stock["qty"], errors="coerce").fillna(0.0)
        stock["unit_cost"] = pd.to_numeric(stock["unit_cost"], errors="coerce").fillna(0.0)
        stock["line_stock_value"] = stock["qty"] * stock["unit_cost"]

        parent_rollup = stock.groupby(
            ["parent_product_id", "parent_product_name"], as_index=False
        ).agg(
            total_available_qty=("qty", "sum"),
            stock_value=("line_stock_value", "sum"),
        )
        parent_rollup["avg_unit_cost"] = parent_rollup.apply(
            lambda r: (
                float(r["stock_value"] / r["total_available_qty"])
                if float(r["total_available_qty"]) > 0
                else 0.0
            ),
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
                    columns=[
                        "variant_id",
                        "variant_name",
                        "qty",
                        "unit_cost",
                        "stock_value",
                        "lot_id",
                    ]
                )
                continue
            d["stock_value"] = d["line_stock_value"]
            detail[product_id] = d[
                ["variant_id", "variant_name", "qty", "unit_cost", "stock_value", "lot_id"]
            ].sort_values(["variant_name", "lot_id"])

        return summary, detail
