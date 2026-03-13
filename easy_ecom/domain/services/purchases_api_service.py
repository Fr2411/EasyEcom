from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.domain.services.saleable_items_service import SaleableItemsService
from easy_ecom.domain.services.stock_ledger_service import StockLedgerService
from easy_ecom.data.store.postgres_models import (
    FinanceExpenseModel,
    PurchaseItemModel,
    PurchaseModel,
    SupplierModel,
    TenantSettingsModel,
)


@dataclass
class PurchaseLineInput:
    variant_id: str
    qty: float
    unit_cost: float


@dataclass
class PurchaseCreateInput:
    purchase_date: str
    supplier_id: str
    reference_no: str
    note: str
    lines: list[PurchaseLineInput]
    payment_status: str


class PurchasesApiService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory
        self.saleable_items = SaleableItemsService()
        self.stock_ledger = StockLedgerService(session_factory)

    @staticmethod
    def _to_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _validate_iso_date(value: str) -> str:
        raw = value.strip()
        if not raw:
            raise ValueError("purchase_date is required")
        try:
            date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("purchase_date must be ISO format YYYY-MM-DD") from exc
        return raw

    @staticmethod
    def _normalize_payment_status(value: str) -> str:
        status = value.strip().lower() or "unpaid"
        if status not in {"paid", "unpaid", "partial"}:
            raise ValueError("payment_status must be one of: paid, unpaid, partial")
        return status

    def _purchase_prefix(self, session: Session, client_id: str) -> str:
        cfg = session.execute(
            select(TenantSettingsModel).where(TenantSettingsModel.client_id == client_id)
        ).scalar_one_or_none()
        prefix = "PUR"
        if cfg and str(cfg.purchases_prefix or "").strip():
            prefix = str(cfg.purchases_prefix).strip().upper()
        return "".join(ch for ch in prefix if ch.isalnum())[:12] or "PUR"

    def lookup_options(self, *, client_id: str, query: str = "") -> dict[str, object]:
        q = query.strip()
        with self.session_factory() as session:
            items = self.saleable_items.list_saleable_variants(
                session=session,
                client_id=client_id,
                query=q,
                include_out_of_stock=True,
                limit=120,
            ) if q else []
            products = [
                {
                    "variant_id": str(item["variant_id"]),
                    "product_id": str(item["product_id"]),
                    "label": f"{item['product_name']} / {item['variant_name']} / {item['sku']}",
                    "current_stock": float(item["available_qty"]),
                    "sku": str(item["sku"]),
                    "barcode": str(item["barcode"]),
                }
                for item in items
            ]

            supplier_stmt = select(SupplierModel).where(
                SupplierModel.client_id == client_id,
                SupplierModel.is_active == "true",
            )
            if q:
                supplier_stmt = supplier_stmt.where(SupplierModel.name.ilike(f"%{q}%"))
            suppliers = session.execute(supplier_stmt.order_by(SupplierModel.name.asc()).limit(100)).scalars().all()

        return {
            "products": products,
            "suppliers": [{"supplier_id": row.supplier_id, "name": row.name} for row in suppliers],
        }

    def list_purchases(self, *, client_id: str, query: str = "") -> list[dict[str, object]]:
        with self.session_factory() as session:
            stmt = (
                select(PurchaseModel, SupplierModel)
                .outerjoin(
                    SupplierModel,
                    and_(
                        SupplierModel.client_id == PurchaseModel.client_id,
                        SupplierModel.supplier_id == PurchaseModel.supplier_id,
                    ),
                )
                .where(PurchaseModel.client_id == client_id)
            )
            if query.strip():
                needle = f"%{query.strip()}%"
                stmt = stmt.where(
                    or_(
                        PurchaseModel.purchase_no.ilike(needle),
                        PurchaseModel.purchase_date.ilike(needle),
                        PurchaseModel.reference_no.ilike(needle),
                        PurchaseModel.supplier_name_snapshot.ilike(needle),
                        SupplierModel.name.ilike(needle),
                        PurchaseModel.purchase_id.in_(
                            select(PurchaseItemModel.purchase_id).where(
                                PurchaseItemModel.client_id == client_id,
                                or_(
                                    PurchaseItemModel.product_name_snapshot.ilike(needle),
                                    PurchaseItemModel.product_id.ilike(needle),
                                ),
                            )
                        ),
                    )
                )
            rows = session.execute(stmt.order_by(PurchaseModel.created_at.desc()).limit(200)).all()
            purchase_ids = [row.purchase_id for row, _ in rows]
            item_rows = session.execute(
                select(PurchaseItemModel).where(
                    PurchaseItemModel.client_id == client_id,
                    PurchaseItemModel.purchase_id.in_(purchase_ids or ["__none__"]),
                )
            ).scalars().all()

        products_map: dict[str, set[str]] = {}
        for item in item_rows:
            products_map.setdefault(item.purchase_id, set()).add(str(item.product_name_snapshot))

        items: list[dict[str, object]] = []
        for purchase, supplier in rows:
            product_preview = ", ".join(sorted(products_map.get(purchase.purchase_id, set())))
            items.append(
                {
                    "purchase_id": purchase.purchase_id,
                    "purchase_no": purchase.purchase_no,
                    "purchase_date": purchase.purchase_date,
                    "supplier_id": purchase.supplier_id,
                    "supplier_name": supplier.name if supplier else purchase.supplier_name_snapshot,
                    "reference_no": purchase.reference_no,
                    "subtotal": self._to_float(purchase.subtotal),
                    "status": purchase.status,
                    "created_at": purchase.created_at,
                    "product_preview": product_preview,
                }
            )
        return items

    def get_purchase_detail(self, *, client_id: str, purchase_id: str) -> dict[str, object] | None:
        with self.session_factory() as session:
            purchase = session.execute(
                select(PurchaseModel).where(
                    PurchaseModel.client_id == client_id,
                    PurchaseModel.purchase_id == purchase_id,
                )
            ).scalar_one_or_none()
            if purchase is None:
                return None
            supplier = None
            if purchase.supplier_id:
                supplier = session.execute(
                    select(SupplierModel).where(
                        SupplierModel.client_id == client_id,
                        SupplierModel.supplier_id == purchase.supplier_id,
                    )
                ).scalar_one_or_none()
            lines = session.execute(
                select(PurchaseItemModel).where(
                    PurchaseItemModel.client_id == client_id,
                    PurchaseItemModel.purchase_id == purchase_id,
                )
            ).scalars().all()

        return {
            "purchase_id": purchase.purchase_id,
            "purchase_no": purchase.purchase_no,
            "purchase_date": purchase.purchase_date,
            "supplier_id": purchase.supplier_id,
            "supplier_name": supplier.name if supplier else purchase.supplier_name_snapshot,
            "reference_no": purchase.reference_no,
            "subtotal": self._to_float(purchase.subtotal),
            "status": purchase.status,
            "created_at": purchase.created_at,
            "created_by_user_id": purchase.created_by_user_id,
            "note": purchase.note,
            "lines": [
                {
                    "line_id": line.purchase_item_id,
                    "product_id": line.product_id,
                    "variant_id": line.variant_id,
                    "product_name": line.product_name_snapshot,
                    "qty": self._to_float(line.qty),
                    "unit_cost": self._to_float(line.unit_cost),
                    "line_total": self._to_float(line.line_total),
                }
                for line in lines
            ],
        }

    def create_purchase(self, *, client_id: str, user_id: str, payload: PurchaseCreateInput) -> dict[str, object]:
        if not payload.lines:
            raise ValueError("At least one purchase line is required")

        purchase_date = self._validate_iso_date(payload.purchase_date)
        payment_status = self._normalize_payment_status(payload.payment_status)
        purchase_id = new_uuid()

        with self.session_factory() as session:
            prefix = self._purchase_prefix(session, client_id)
            purchase_no = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{purchase_id[:6].upper()}"

            supplier_name = ""
            supplier_id = payload.supplier_id.strip()
            if supplier_id:
                supplier = session.execute(
                    select(SupplierModel).where(
                        SupplierModel.client_id == client_id,
                        SupplierModel.supplier_id == supplier_id,
                        SupplierModel.is_active == "true",
                    )
                ).scalar_one_or_none()
                if supplier is None:
                    raise ValueError("Invalid supplier for tenant")
                supplier_name = supplier.name

            subtotal = 0.0
            item_entities: list[PurchaseItemModel] = []
            line_posts: list[tuple[PurchaseItemModel, float, float]] = []
            for line in payload.lines:
                if line.qty <= 0:
                    raise ValueError("Purchase quantity must be > 0")
                if line.unit_cost < 0:
                    raise ValueError("Purchase unit_cost must be >= 0")
                variant = self.stock_ledger.resolve_variant(
                    session,
                    client_id=client_id,
                    variant_id=line.variant_id,
                )
                line_total = float(line.qty) * float(line.unit_cost)
                subtotal += line_total
                item_entity = PurchaseItemModel(
                    purchase_item_id=new_uuid(),
                    purchase_id=purchase_id,
                    client_id=client_id,
                    product_id=variant.product_id,
                    variant_id=variant.variant_id,
                    product_name_snapshot=f"{variant.product_name} / {variant.variant_name}",
                    qty=str(line.qty),
                    unit_cost=str(line.unit_cost),
                    line_total=str(line_total),
                )
                item_entities.append(item_entity)
                line_posts.append((item_entity, float(line.qty), float(line.unit_cost)))

            purchase = PurchaseModel(
                purchase_id=purchase_id,
                client_id=client_id,
                purchase_no=purchase_no,
                purchase_date=purchase_date,
                supplier_id=supplier_id,
                supplier_name_snapshot=supplier_name,
                reference_no=payload.reference_no.strip(),
                status="received",
                subtotal=str(subtotal),
                note=payload.note.strip(),
                created_at=now_iso(),
                created_by_user_id=user_id,
            )
            session.add(purchase)
            session.add_all(item_entities)

            for line, qty, unit_cost in line_posts:
                variant = self.stock_ledger.resolve_variant(
                    session,
                    client_id=client_id,
                    variant_id=line.variant_id,
                )
                self.stock_ledger.post_inbound(
                    session=session,
                    client_id=client_id,
                    user_id=user_id,
                    variant=variant,
                    qty=qty,
                    unit_cost=unit_cost,
                    supplier_snapshot=supplier_name,
                    note=f"purchase:{purchase_no}",
                    source_type="purchase",
                    source_id=purchase_id,
                    source_line_id=line.purchase_item_id,
                )

            session.add(
                FinanceExpenseModel(
                    expense_id=new_uuid(),
                    client_id=client_id,
                    expense_date=purchase_date,
                    category="Purchases",
                    amount=str(subtotal),
                    payment_status=payment_status,
                    note=f"Purchase {purchase_no} {payload.note.strip()}".strip(),
                    created_by_user_id=user_id,
                    created_at=now_iso(),
                    updated_at=now_iso(),
                )
            )
            session.commit()

        return {
            "purchase_id": purchase_id,
            "purchase_no": purchase_no,
            "subtotal": subtotal,
            "status": "received",
        }
