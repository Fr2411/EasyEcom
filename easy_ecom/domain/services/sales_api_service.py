from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from collections import defaultdict

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.store.postgres_models import (
    CustomerModel,
    InventoryTxnModel,
    SalesOrderItemModel,
    SalesOrderModel,
)
from easy_ecom.domain.services.saleable_items_service import SaleableItemsService


@dataclass
class SalesLineInput:
    variant_id: str
    qty: float
    unit_price: float


class SalesApiService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory
        self.saleable_items = SaleableItemsService()

    def _stock_for_variant(self, session: Session, client_id: str, variant_id: str) -> float:
        items = self.saleable_items.list_saleable_variants(
            session=session,
            client_id=client_id,
            query=variant_id,
            include_out_of_stock=True,
            limit=1,
        )
        for item in items:
            if item["variant_id"] == variant_id:
                return float(item["available_qty"])
        return 0.0

    def lookup_customers(self, client_id: str, query: str = "") -> list[dict[str, str]]:
        with self.session_factory() as session:
            stmt = select(CustomerModel).where(CustomerModel.client_id == client_id)
            if query.strip():
                needle = f"%{query.strip()}%"
                stmt = stmt.where(
                    CustomerModel.full_name.ilike(needle)
                    | CustomerModel.phone.ilike(needle)
                    | CustomerModel.email.ilike(needle)
                )
            rows = session.execute(stmt.order_by(CustomerModel.full_name.asc()).limit(100)).scalars().all()
        return [
            {
                "customer_id": row.customer_id,
                "full_name": row.full_name,
                "phone": row.phone,
                "email": row.email,
            }
            for row in rows
        ]

    def lookup_products(self, client_id: str, query: str = "") -> list[dict[str, str | float]]:
        with self.session_factory() as session:
            items = self.saleable_items.list_saleable_variants(
                session=session,
                client_id=client_id,
                query=query,
                include_out_of_stock=False,
                limit=120,
            )
        return [
            {
                "variant_id": str(item["variant_id"]),
                "product_id": str(item["product_id"]),
                "label": f"{item['product_name']} / {item['variant_name']} / {item['sku']}",
                "sku": str(item["sku"]),
                "barcode": str(item["barcode"]),
                "product_name": str(item["product_name"]),
                "variant_name": str(item["variant_name"]),
                "default_unit_price": float(item["default_selling_price"]),
                "available_qty": float(item["available_qty"]),
            }
            for item in items
        ]

    def list_sales(self, client_id: str, query: str = "") -> list[dict[str, str | float]]:
        with self.session_factory() as session:
            stmt = select(SalesOrderModel, CustomerModel).outerjoin(
                CustomerModel,
                (CustomerModel.customer_id == SalesOrderModel.customer_id) & (CustomerModel.client_id == SalesOrderModel.client_id),
            ).where(SalesOrderModel.client_id == client_id)
            if query.strip():
                needle = f"%{query.strip()}%"
                stmt = stmt.where(
                    SalesOrderModel.sale_no.ilike(needle)
                    | CustomerModel.full_name.ilike(needle)
                    | SalesOrderModel.timestamp.ilike(needle)
                )
            rows = session.execute(stmt.order_by(SalesOrderModel.timestamp.desc()).limit(200)).all()
        return [
            {
                "sale_id": order.order_id,
                "sale_no": order.sale_no,
                "customer_id": order.customer_id,
                "customer_name": customer.full_name if customer else "",
                "timestamp": order.timestamp,
                "subtotal": float(order.subtotal or "0"),
                "discount": float(order.discount or "0"),
                "tax": float(order.tax or "0"),
                "total": float(order.grand_total or "0"),
                "status": order.status,
            }
            for order, customer in rows
        ]

    def get_sale_detail(self, client_id: str, sale_id: str) -> dict[str, object] | None:
        with self.session_factory() as session:
            order = session.execute(
                select(SalesOrderModel).where(SalesOrderModel.client_id == client_id, SalesOrderModel.order_id == sale_id)
            ).scalar_one_or_none()
            if order is None:
                return None
            customer = session.execute(
                select(CustomerModel).where(CustomerModel.client_id == client_id, CustomerModel.customer_id == order.customer_id)
            ).scalar_one_or_none()
            items = session.execute(
                select(SalesOrderItemModel).where(SalesOrderItemModel.client_id == client_id, SalesOrderItemModel.order_id == order.order_id)
            ).scalars().all()
        return {
            "sale_id": order.order_id,
            "sale_no": order.sale_no,
            "customer_id": order.customer_id,
            "customer_name": customer.full_name if customer else "",
            "timestamp": order.timestamp,
            "subtotal": float(order.subtotal or "0"),
            "discount": float(order.discount or "0"),
            "tax": float(order.tax or "0"),
            "total": float(order.grand_total or "0"),
            "status": order.status,
            "note": order.note,
            "lines": [
                {
                    "line_id": item.order_item_id,
                    "product_id": item.product_id,
                    "variant_id": item.variant_id,
                    "product_name": item.product_name_snapshot,
                    "qty": float(item.qty or "0"),
                    "unit_price": float(item.unit_selling_price or "0"),
                    "line_total": float(item.total_selling_price or "0"),
                }
                for item in items
            ],
        }

    def create_sale(
        self,
        *,
        client_id: str,
        user_id: str,
        customer_id: str,
        lines: list[SalesLineInput],
        discount: float,
        tax: float,
        note: str,
    ) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        sale_id = new_uuid()
        sale_no = f"SAL-{now.strftime('%Y%m%d')}-{sale_id[:6].upper()}"

        with self.session_factory() as session:
            customer = session.execute(
                select(CustomerModel).where(CustomerModel.client_id == client_id, CustomerModel.customer_id == customer_id)
            ).scalar_one_or_none()
            if customer is None:
                raise ValueError("Invalid customer for tenant")

            line_entities: list[SalesOrderItemModel] = []
            subtotal = 0.0
            requested_by_variant: dict[str, float] = defaultdict(float)
            for line in lines:
                requested_by_variant[line.variant_id] += line.qty

            for variant_id, requested_qty in requested_by_variant.items():
                available = self._stock_for_variant(session, client_id, variant_id)
                if available < requested_qty:
                    raise ValueError(f"Insufficient stock for variant {variant_id}")

            saleable_map = {
                str(item["variant_id"]): item
                for item in self.saleable_items.list_saleable_variants(
                    session=session,
                    client_id=client_id,
                    query="",
                    include_out_of_stock=True,
                    limit=10000,
                )
            }

            for line in lines:
                if line.qty <= 0 or line.unit_price < 0:
                    raise ValueError("Invalid sale line payload")
                item = saleable_map.get(line.variant_id)
                if item is None:
                    raise ValueError(f"Invalid variant reference: {line.variant_id}")
                total = float(line.qty) * float(line.unit_price)
                subtotal += total
                line_entities.append(
                    SalesOrderItemModel(
                        order_item_id=new_uuid(),
                        order_id=sale_id,
                        client_id=client_id,
                        product_id=str(item["product_id"]),
                        variant_id=line.variant_id,
                        product_name_snapshot=f"{item['product_name']} / {item['variant_name']}",
                        qty=str(line.qty),
                        unit_selling_price=str(line.unit_price),
                        total_selling_price=str(total),
                    )
                )

            grand_total = max(0.0, subtotal - max(0.0, discount) + max(0.0, tax))
            order = SalesOrderModel(
                order_id=sale_id,
                client_id=client_id,
                sale_no=sale_no,
                timestamp=now_iso(),
                customer_id=customer_id,
                status="confirmed",
                subtotal=str(subtotal),
                discount=str(max(0.0, discount)),
                tax=str(max(0.0, tax)),
                grand_total=str(grand_total),
                amount_paid="0",
                outstanding_balance=str(grand_total),
                payment_status="unpaid",
                note=note.strip(),
                created_by_user_id=user_id,
            )
            session.add(order)
            session.add_all(line_entities)

            for line in line_entities:
                session.add(
                    InventoryTxnModel(
                        txn_id=new_uuid(),
                        client_id=client_id,
                        timestamp=now_iso(),
                        user_id=user_id,
                        txn_type="OUT",
                        product_id=line.product_id,
                        variant_id=line.variant_id,
                        product_name=line.product_name_snapshot,
                        qty=line.qty,
                        unit_cost="0",
                        total_cost="0",
                        supplier_snapshot="",
                        note=f"sale:{sale_no}",
                        source_type="sale",
                        source_id=sale_id,
                        lot_id="",
                    )
                )
            session.commit()

        return {
            "sale_id": sale_id,
            "sale_no": sale_no,
            "total": grand_total,
            "status": "confirmed",
        }
