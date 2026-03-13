from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import current_year, now_iso
from easy_ecom.data.store.postgres_models import InventoryTxnModel, ProductModel, ProductVariantModel
from easy_ecom.domain.services.stock_policy import stock_deltas


@dataclass(frozen=True)
class VariantContext:
    product_id: str
    product_name: str
    variant_id: str
    variant_name: str


class StockLedgerService:
    """Canonical lot-aware inventory write path for Postgres-backed flows."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    @staticmethod
    def _to_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def resolve_variant(self, session: Session, *, client_id: str, variant_id: str) -> VariantContext:
        row = session.execute(
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
                ProductVariantModel.variant_id == variant_id,
            )
        ).first()
        if row is None:
            raise ValueError(f"Invalid variant reference: {variant_id}")
        variant, product = row
        return VariantContext(
            product_id=str(product.product_id),
            product_name=str(product.product_name or "").strip() or str(product.product_id),
            variant_id=str(variant.variant_id),
            variant_name=str(variant.variant_name or "").strip() or str(variant.variant_id),
        )

    def new_lot_id(self) -> str:
        return f"LOT-{current_year()}-{new_uuid()[:8].upper()}"

    def new_inbound_id(self) -> str:
        return f"INB-{current_year()}-{new_uuid()[:8].upper()}"

    def post_inbound(
        self,
        *,
        session: Session,
        client_id: str,
        user_id: str,
        variant: VariantContext,
        qty: float,
        unit_cost: float,
        supplier_snapshot: str,
        note: str,
        source_type: str,
        source_id: str,
        source_line_id: str = "",
        lot_id: str | None = None,
        txn_type: str = "IN",
    ) -> str:
        quantity = float(qty)
        cost = float(unit_cost)
        if quantity <= 0:
            raise ValueError("qty must be > 0")
        if txn_type == "IN" and cost <= 0:
            raise ValueError("unit_cost must be > 0")
        resolved_lot_id = str(lot_id or "").strip() or self.new_lot_id()
        session.add(
            InventoryTxnModel(
                txn_id=new_uuid(),
                client_id=client_id,
                timestamp=now_iso(),
                user_id=user_id,
                txn_type=txn_type,
                product_id=variant.product_id,
                variant_id=variant.variant_id,
                product_name=variant.variant_name,
                qty=str(quantity),
                unit_cost=str(cost),
                total_cost=str(quantity * cost),
                supplier_snapshot=supplier_snapshot,
                note=note,
                source_type=source_type,
                source_id=source_id,
                source_line_id=source_line_id,
                lot_id=resolved_lot_id,
            )
        )
        return resolved_lot_id

    def create_pending_inbound(
        self,
        *,
        session: Session,
        client_id: str,
        user_id: str,
        variant: VariantContext,
        qty: float,
        unit_cost: float,
        supplier_snapshot: str,
        note: str,
        reference: str,
    ) -> str:
        inbound_id = self.new_inbound_id()
        pending_note_parts = [note.strip()]
        if reference.strip():
            pending_note_parts.append(f"ref:{reference.strip()}")
        pending_note = " | ".join(part for part in pending_note_parts if part)
        self.post_inbound(
            session=session,
            client_id=client_id,
            user_id=user_id,
            variant=variant,
            qty=qty,
            unit_cost=unit_cost,
            supplier_snapshot=supplier_snapshot,
            note=pending_note,
            source_type="inbound_pending",
            source_id=inbound_id,
            txn_type="INBOUND_PENDING",
        )
        return inbound_id

    def receive_pending_inbound(
        self,
        *,
        session: Session,
        client_id: str,
        user_id: str,
        inbound_id: str,
        qty: float | None,
        unit_cost: float | None,
        note: str,
    ) -> tuple[str, str, float]:
        pending_rows = session.execute(
            select(InventoryTxnModel).where(
                InventoryTxnModel.client_id == client_id,
                InventoryTxnModel.source_type == "inbound_pending",
                InventoryTxnModel.source_id == inbound_id,
            )
        ).scalars().all()
        if not pending_rows:
            raise ValueError("Inbound record not found")

        all_rows = session.execute(
            select(InventoryTxnModel).where(
                InventoryTxnModel.client_id == client_id,
                InventoryTxnModel.source_id == inbound_id,
                InventoryTxnModel.source_type.in_(["inbound_pending", "inbound_pending_release"]),
            )
        ).scalars().all()

        seed = pending_rows[0]
        variant = VariantContext(
            product_id=str(seed.product_id),
            product_name="",
            variant_id=str(seed.variant_id),
            variant_name=str(seed.product_name or seed.variant_id),
        )
        pending_qty = 0.0
        for row in all_rows:
            pending_qty += stock_deltas(str(row.txn_type), self._to_float(row.qty)).incoming
        if pending_qty <= 0:
            raise ValueError("Inbound record not found")

        received_qty = float(qty) if qty is not None else pending_qty
        if received_qty <= 0:
            raise ValueError("Received quantity must be > 0")
        if received_qty > pending_qty:
            raise ValueError("Received quantity cannot exceed pending incoming quantity")

        receiving_cost = float(unit_cost) if unit_cost is not None else self._to_float(seed.unit_cost)
        if receiving_cost <= 0:
            raise ValueError("unit_cost is required")

        lot_id = str(seed.lot_id or "").strip() or self.new_lot_id()
        release_note = f"Inbound received: {note}".strip()
        self.post_inbound(
            session=session,
            client_id=client_id,
            user_id=user_id,
            variant=variant,
            qty=received_qty,
            unit_cost=self._to_float(seed.unit_cost) or receiving_cost,
            supplier_snapshot="",
            note=release_note,
            source_type="inbound_pending_release",
            source_id=inbound_id,
            txn_type="INBOUND_RECEIVED",
            lot_id=lot_id,
        )
        self.post_inbound(
            session=session,
            client_id=client_id,
            user_id=user_id,
            variant=variant,
            qty=received_qty,
            unit_cost=receiving_cost,
            supplier_snapshot=str(seed.supplier_snapshot or ""),
            note=release_note,
            source_type="inbound_receive",
            source_id=inbound_id,
            lot_id=lot_id,
        )
        return variant.variant_id, lot_id, received_qty

    def available_lots(
        self,
        *,
        session: Session,
        client_id: str,
        variant_id: str,
    ) -> list[dict[str, object]]:
        rows = session.execute(
            select(InventoryTxnModel)
            .where(
                InventoryTxnModel.client_id == client_id,
                InventoryTxnModel.variant_id == variant_id,
            )
            .order_by(InventoryTxnModel.timestamp.asc(), InventoryTxnModel.txn_id.asc())
        ).scalars().all()

        lots: dict[str, dict[str, object]] = {}
        for row in rows:
            lot_id = str(row.lot_id or "").strip()
            if not lot_id:
                continue
            record = lots.setdefault(
                lot_id,
                {
                    "lot_id": lot_id,
                    "product_id": str(row.product_id or ""),
                    "product_name": str(row.product_name or ""),
                    "variant_id": str(row.variant_id or ""),
                    "unit_cost": self._to_float(row.unit_cost),
                    "qty": 0.0,
                    "first_seen": str(row.timestamp or ""),
                },
            )
            delta = stock_deltas(str(row.txn_type), self._to_float(row.qty))
            record["qty"] = self._to_float(record["qty"]) + delta.on_hand
            if self._to_float(row.unit_cost) > 0 and str(row.txn_type).upper() in {"IN", "ADJUST", "ADJUST+"}:
                record["unit_cost"] = self._to_float(row.unit_cost)
            if str(row.timestamp or "") and (
                not str(record["first_seen"]) or str(row.timestamp) < str(record["first_seen"])
            ):
                record["first_seen"] = str(row.timestamp)

        return [
            row
            for row in sorted(lots.values(), key=lambda item: (str(item["first_seen"]), str(item["lot_id"])))
            if self._to_float(row["qty"]) > 0
        ]

    def consume_fifo(
        self,
        *,
        session: Session,
        client_id: str,
        user_id: str,
        variant: VariantContext,
        qty: float,
        source_type: str,
        source_id: str,
        source_line_id: str = "",
        note: str = "",
    ) -> list[dict[str, float | str]]:
        requested = float(qty)
        if requested <= 0:
            raise ValueError("qty must be positive")
        lots = self.available_lots(session=session, client_id=client_id, variant_id=variant.variant_id)
        remaining = requested
        allocations: list[dict[str, float | str]] = []
        for lot in lots:
            if remaining <= 0:
                break
            available = self._to_float(lot["qty"])
            take = min(available, remaining)
            if take <= 0:
                continue
            unit_cost = self._to_float(lot["unit_cost"])
            session.add(
                InventoryTxnModel(
                    txn_id=new_uuid(),
                    client_id=client_id,
                    timestamp=now_iso(),
                    user_id=user_id,
                    txn_type="OUT",
                    product_id=variant.product_id,
                    variant_id=variant.variant_id,
                    product_name=variant.variant_name,
                    qty=str(take),
                    unit_cost=str(unit_cost),
                    total_cost=str(take * unit_cost),
                    supplier_snapshot="",
                    note=note,
                    source_type=source_type,
                    source_id=source_id,
                    source_line_id=source_line_id,
                    lot_id=str(lot["lot_id"]),
                )
            )
            allocations.append(
                {
                    "lot_id": str(lot["lot_id"]),
                    "qty": take,
                    "unit_cost": unit_cost,
                }
            )
            remaining -= take
        if remaining > 0:
            raise ValueError("Insufficient stock for selected variant")
        return allocations

    def restore_sale_line(
        self,
        *,
        session: Session,
        client_id: str,
        user_id: str,
        sale_line_id: str,
        qty: float,
        source_id: str,
        note: str,
    ) -> list[dict[str, float | str]]:
        requested = float(qty)
        if requested <= 0:
            raise ValueError("qty must be positive")

        sold_rows = session.execute(
            select(InventoryTxnModel)
            .where(
                InventoryTxnModel.client_id == client_id,
                InventoryTxnModel.source_type == "sale",
                InventoryTxnModel.source_line_id == sale_line_id,
            )
            .order_by(InventoryTxnModel.timestamp.asc(), InventoryTxnModel.txn_id.asc())
        ).scalars().all()
        if not sold_rows:
            raise ValueError("No sale allocations found for return line")

        returned_rows = session.execute(
            select(InventoryTxnModel)
            .where(
                InventoryTxnModel.client_id == client_id,
                InventoryTxnModel.source_type == "sale_return",
                InventoryTxnModel.source_line_id == sale_line_id,
            )
        ).scalars().all()
        returned_by_lot: dict[str, float] = defaultdict(float)
        for row in returned_rows:
            returned_by_lot[str(row.lot_id or "")] += self._to_float(row.qty)

        remaining = requested
        restorations: list[dict[str, float | str]] = []
        for row in sold_rows:
            if remaining <= 0:
                break
            lot_id = str(row.lot_id or "").strip()
            sold_qty = self._to_float(row.qty)
            eligible = max(0.0, sold_qty - returned_by_lot.get(lot_id, 0.0))
            if eligible <= 0:
                continue
            put_back = min(eligible, remaining)
            session.add(
                InventoryTxnModel(
                    txn_id=new_uuid(),
                    client_id=client_id,
                    timestamp=now_iso(),
                    user_id=user_id,
                    txn_type="IN",
                    product_id=str(row.product_id or ""),
                    variant_id=str(row.variant_id or ""),
                    product_name=str(row.product_name or row.variant_id or ""),
                    qty=str(put_back),
                    unit_cost=str(self._to_float(row.unit_cost)),
                    total_cost=str(put_back * self._to_float(row.unit_cost)),
                    supplier_snapshot="",
                    note=note,
                    source_type="sale_return",
                    source_id=source_id,
                    source_line_id=sale_line_id,
                    lot_id=lot_id,
                )
            )
            returned_by_lot[lot_id] += put_back
            restorations.append(
                {
                    "lot_id": lot_id,
                    "qty": put_back,
                    "unit_cost": self._to_float(row.unit_cost),
                }
            )
            remaining -= put_back
        if remaining > 0:
            raise ValueError("Return quantity exceeds original sale allocations")
        return restorations
