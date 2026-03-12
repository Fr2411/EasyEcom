from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from easy_ecom.data.store.postgres_models import InventoryTxnModel, ProductModel, ProductVariantModel
from easy_ecom.domain.services.stock_policy import stock_deltas


class SaleableItemsService:
    """Canonical stock aggregation for variant-level saleable inventory."""

    @staticmethod
    def _to_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def list_saleable_variants(
        self,
        *,
        session: Session,
        client_id: str,
        query: str = "",
        variant_ids: list[str] | None = None,
        include_out_of_stock: bool = False,
        limit: int = 120,
    ) -> list[dict[str, object]]:
        q = query.strip()
        scoped_variant_ids = [str(v).strip() for v in (variant_ids or []) if str(v).strip()]

        stmt = (
            select(ProductVariantModel, ProductModel)
            .join(
                ProductModel,
                and_(
                    ProductModel.client_id == ProductVariantModel.client_id,
                    ProductModel.product_id == ProductVariantModel.parent_product_id,
                ),
            )
            .where(
                ProductVariantModel.client_id == client_id,
                ProductVariantModel.is_active == "true",
                ProductModel.is_active == "true",
            )
        )

        if scoped_variant_ids:
            stmt = stmt.where(ProductVariantModel.variant_id.in_(scoped_variant_ids))

        if q:
            needle = f"%{q}%"
            stmt = stmt.where(
                or_(
                    ProductVariantModel.sku_code.ilike(needle),
                    ProductVariantModel.variant_name.ilike(needle),
                    ProductVariantModel.barcode.ilike(needle),
                    ProductModel.product_name.ilike(needle),
                )
            )
        elif not include_out_of_stock and not scoped_variant_ids:
            return []

        rows = session.execute(stmt.limit(limit)).all()
        variant_ids = [variant.variant_id for variant, _ in rows]
        stock: dict[str, float] = {vid: 0.0 for vid in variant_ids}
        if variant_ids:
            txn_rows = session.execute(
                select(InventoryTxnModel.variant_id, InventoryTxnModel.txn_type, InventoryTxnModel.qty).where(
                    InventoryTxnModel.client_id == client_id,
                    InventoryTxnModel.variant_id.in_(variant_ids),
                )
            ).all()
            for variant_id, txn_type, qty in txn_rows:
                stock[str(variant_id)] = stock.get(str(variant_id), 0.0) + stock_deltas(str(txn_type), self._to_float(qty)).on_hand

        items: list[dict[str, object]] = []
        for variant, product in rows:
            available = stock.get(variant.variant_id, 0.0)
            if not include_out_of_stock and available <= 0:
                continue
            items.append(
                {
                    "variant_id": variant.variant_id,
                    "product_id": product.product_id,
                    "sku": (variant.sku_code or "").strip(),
                    "barcode": (variant.barcode or "").strip(),
                    "product_name": product.product_name,
                    "variant_name": variant.variant_name,
                    "variant_display_name": variant.variant_name,
                    "available_qty": float(available),
                    "selling_price": self._to_float(variant.default_selling_price),
                    "default_selling_price": self._to_float(variant.default_selling_price),
                    "is_active": str(variant.is_active).lower() == "true",
                }
            )
        return items
