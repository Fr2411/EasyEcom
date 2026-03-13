from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.store.postgres_models import InventoryTxnModel, ProductVariantModel

if TYPE_CHECKING:
    from easy_ecom.domain.services.catalog_stock_service import VariantWorkspaceEntry


class CatalogStockPostgresRepo:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def persist_workspace_rows(
        self,
        *,
        client_id: str,
        user_id: str,
        product_id: str,
        product_name: str,
        entries: list[VariantWorkspaceEntry],
        existing_by_identity: dict[str, str],
    ) -> list[str]:
        lot_ids: list[str] = []
        with self.session_factory.begin() as session:
            for entry in entries:
                variant_id = self._upsert_variant(
                    session=session,
                    client_id=client_id,
                    product_id=product_id,
                    product_name=product_name,
                    entry=entry,
                    existing_variant_id=entry.variant_id or existing_by_identity.get(entry.identity_key(), ""),
                )
                existing_by_identity[entry.identity_key()] = variant_id
                if entry.qty <= 0:
                    continue
                lot_id = self._next_lot_id(session=session, client_id=client_id)
                lot_ids.append(lot_id)
                session.add(
                    InventoryTxnModel(
                        txn_id=new_uuid(),
                        client_id=client_id,
                        timestamp=now_iso(),
                        user_id=user_id,
                        txn_type="IN",
                        product_id=product_id,
                        variant_id=variant_id,
                        product_name=f"{product_name} | "
                        + " | ".join(
                            [
                                part
                                for part in [
                                    f"Size:{entry.size}" if entry.size else "",
                                    f"Color:{entry.color}" if entry.color else "",
                                    f"Other:{entry.other}" if entry.other else "",
                                ]
                                if part
                            ]
                        ),
                        qty=str(entry.qty),
                        unit_cost=str(entry.unit_cost),
                        total_cost=str(entry.qty * entry.unit_cost),
                        supplier_snapshot=entry.supplier,
                        note=" | ".join(
                            [
                                p
                                for p in [
                                    f"ref:{entry.lot_reference}" if entry.lot_reference else "",
                                    f"received:{entry.received_date}" if entry.received_date else "",
                                ]
                                if p
                            ]
                        ),
                        source_type="catalog_stock",
                        source_id=entry.lot_reference,
                        lot_id=lot_id,
                    )
                )
        return lot_ids

    def _upsert_variant(
        self,
        *,
        session: Session,
        client_id: str,
        product_id: str,
        product_name: str,
        entry: VariantWorkspaceEntry,
        existing_variant_id: str,
    ) -> str:
        variant = None
        if existing_variant_id:
            variant = session.execute(
                select(ProductVariantModel).where(
                    and_(
                        ProductVariantModel.client_id == client_id,
                        ProductVariantModel.parent_product_id == product_id,
                        ProductVariantModel.variant_id == existing_variant_id,
                    )
                )
            ).scalar_one_or_none()
        if variant is None:
            variant = session.execute(
                select(ProductVariantModel).where(
                    and_(
                        ProductVariantModel.client_id == client_id,
                        ProductVariantModel.parent_product_id == product_id,
                        func.lower(ProductVariantModel.size) == entry.size.lower(),
                        func.lower(ProductVariantModel.color) == entry.color.lower(),
                        func.lower(ProductVariantModel.other) == entry.other.lower(),
                    )
                )
            ).scalar_one_or_none()

        variant_name = self._variant_name(product_name, entry)
        if variant is None:
            variant = ProductVariantModel(
                variant_id=new_uuid(),
                client_id=client_id,
                parent_product_id=product_id,
                variant_name=variant_name,
                size=entry.size,
                color=entry.color,
                other=entry.other,
                sku_code=f"SKU-{new_uuid()[:8].upper()}",
                default_selling_price=str(entry.default_selling_price),
                max_discount_pct=str(entry.max_discount_pct),
                is_active="true",
                created_at=now_iso(),
            )
            session.add(variant)
        else:
            variant.size = entry.size
            variant.color = entry.color
            variant.other = entry.other
            variant.variant_name = variant_name
            variant.default_selling_price = str(entry.default_selling_price)
            variant.max_discount_pct = str(entry.max_discount_pct)
        return str(variant.variant_id)

    @staticmethod
    def _variant_name(product_name: str, entry: VariantWorkspaceEntry) -> str:
        parts: list[str] = []
        if entry.size:
            parts.append(f"Size:{entry.size}")
        if entry.color:
            parts.append(f"Color:{entry.color}")
        if entry.other:
            parts.append(f"Other:{entry.other}")
        suffix = " | ".join(parts) if parts else "Default"
        return f"{product_name} | {suffix}" if product_name else suffix

    def _next_lot_id(self, *, session: Session, client_id: str) -> str:
        year = now_iso()[:4]
        rows = session.execute(
            select(InventoryTxnModel.lot_id).where(
                and_(
                    InventoryTxnModel.client_id == client_id,
                    InventoryTxnModel.lot_id.like(f"LOT-{year}-%"),
                    or_(InventoryTxnModel.lot_id.is_not(None), InventoryTxnModel.lot_id != ""),
                )
            )
        ).all()
        max_no = 0
        for row in rows:
            lot_id = str(row[0] or "")
            try:
                max_no = max(max_no, int(lot_id.split("-")[-1]))
            except Exception:
                continue
        return f"LOT-{year}-{max_no + 1:05d}"
