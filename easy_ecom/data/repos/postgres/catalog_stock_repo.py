from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.store.postgres_models import ProductVariantModel
from easy_ecom.domain.services.stock_ledger_service import StockLedgerService, VariantContext

if TYPE_CHECKING:
    from easy_ecom.domain.services.catalog_stock_service import VariantWorkspaceEntry


class CatalogStockPostgresRepo:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory
        self.stock_ledger = StockLedgerService(session_factory)

    def persist_workspace_rows(
        self,
        *,
        client_id: str,
        user_id: str,
        product_id: str,
        product_name: str,
        entries: list[VariantWorkspaceEntry],
        existing_by_identity: dict[str, str],
        post_stock: bool = True,
        archive_variant_ids: list[str] | None = None,
    ) -> list[str]:
        lot_ids: list[str] = []
        scoped_archive_variant_ids = [
            str(variant_id).strip()
            for variant_id in (archive_variant_ids or [])
            if str(variant_id).strip()
        ]
        with self.session_factory.begin() as session:
            for entry in entries:
                variant = self._upsert_variant(
                    session=session,
                    client_id=client_id,
                    product_id=product_id,
                    product_name=product_name,
                    entry=entry,
                    existing_variant_id=entry.variant_id or existing_by_identity.get(entry.identity_key(), ""),
                )
                variant_id = str(variant.variant_id)
                existing_by_identity[entry.identity_key()] = variant_id
                if not post_stock or entry.qty <= 0:
                    continue
                lot_ids.append(
                    self.stock_ledger.post_inbound(
                        session=session,
                        client_id=client_id,
                        user_id=user_id,
                        variant=VariantContext(
                            product_id=product_id,
                            product_name=product_name,
                            variant_id=variant_id,
                            variant_name=str(variant.variant_name or variant_id),
                        ),
                        qty=entry.qty,
                        unit_cost=entry.unit_cost,
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
                        source_id=entry.lot_reference or f"catalog-stock:{product_id}",
                    )
                )
            if scoped_archive_variant_ids:
                self._archive_variants(
                    session=session,
                    client_id=client_id,
                    product_id=product_id,
                    archive_variant_ids=scoped_archive_variant_ids,
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
    ) -> ProductVariantModel:
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
                default_purchase_price=str(entry.default_purchase_price),
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
            variant.default_purchase_price = str(entry.default_purchase_price)
            variant.default_selling_price = str(entry.default_selling_price)
            variant.max_discount_pct = str(entry.max_discount_pct)
            variant.is_active = "true"
        return variant

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

    @staticmethod
    def _archive_variants(
        *,
        session: Session,
        client_id: str,
        product_id: str,
        archive_variant_ids: list[str],
    ) -> None:
        rows = session.execute(
            select(ProductVariantModel).where(
                ProductVariantModel.client_id == client_id,
                ProductVariantModel.parent_product_id == product_id,
            )
        ).scalars().all()
        archive = set(
            str(variant_id)
            for variant_id in archive_variant_ids
            if str(variant_id).strip()
        )
        for row in rows:
            if str(row.variant_id) in archive:
                row.is_active = "false"
