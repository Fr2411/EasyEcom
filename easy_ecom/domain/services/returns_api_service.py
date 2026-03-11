from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.store.postgres_models import (
    CustomerModel,
    InventoryTxnModel,
    SalesOrderItemModel,
    SalesOrderModel,
    SalesReturnItemModel,
    SalesReturnModel,
)


@dataclass
class ReturnLineInput:
    sale_item_id: str
    qty: float
    reason: str
    condition_status: str = ""


@dataclass
class ReturnCreateInput:
    sale_id: str
    reason: str
    note: str
    lines: list[ReturnLineInput]


class ReturnsApiService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    @staticmethod
    def _to_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def list_returns(self, *, client_id: str, query: str = "") -> list[dict[str, object]]:
        with self.session_factory() as session:
            stmt = (
                select(SalesReturnModel, CustomerModel)
                .outerjoin(
                    CustomerModel,
                    and_(
                        CustomerModel.client_id == SalesReturnModel.client_id,
                        CustomerModel.customer_id == SalesReturnModel.customer_id,
                    ),
                )
                .where(SalesReturnModel.client_id == client_id)
            )
            if query.strip():
                needle = f"%{query.strip()}%"
                stmt = stmt.where(
                    or_(
                        SalesReturnModel.return_no.ilike(needle),
                        SalesReturnModel.sale_no.ilike(needle),
                        SalesReturnModel.created_at.ilike(needle),
                        CustomerModel.full_name.ilike(needle),
                    )
                )
            rows = session.execute(stmt.order_by(SalesReturnModel.created_at.desc()).limit(200)).all()
        return [
            {
                "return_id": row.return_id,
                "return_no": row.return_no,
                "sale_id": row.sale_id,
                "sale_no": row.sale_no,
                "customer_id": row.customer_id,
                "customer_name": customer.full_name if customer else "",
                "reason": row.reason,
                "return_total": self._to_float(row.return_total),
                "created_at": row.created_at,
            }
            for row, customer in rows
        ]

    def list_sales_for_returns(self, *, client_id: str, query: str = "") -> list[dict[str, object]]:
        with self.session_factory() as session:
            stmt = (
                select(SalesOrderModel, CustomerModel)
                .outerjoin(
                    CustomerModel,
                    and_(
                        CustomerModel.client_id == SalesOrderModel.client_id,
                        CustomerModel.customer_id == SalesOrderModel.customer_id,
                    ),
                )
                .where(SalesOrderModel.client_id == client_id)
            )
            if query.strip():
                needle = f"%{query.strip()}%"
                stmt = stmt.where(
                    or_(
                        SalesOrderModel.sale_no.ilike(needle),
                        SalesOrderModel.timestamp.ilike(needle),
                        CustomerModel.full_name.ilike(needle),
                    )
                )
            rows = session.execute(stmt.order_by(SalesOrderModel.timestamp.desc()).limit(100)).all()

        return [
            {
                "sale_id": sale.order_id,
                "sale_no": sale.sale_no,
                "customer_id": sale.customer_id,
                "customer_name": customer.full_name if customer else "",
                "sale_date": sale.timestamp,
                "total": self._to_float(sale.grand_total),
                "status": sale.status,
            }
            for sale, customer in rows
        ]

    def get_returnable_sale(self, *, client_id: str, sale_id: str) -> dict[str, object] | None:
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
                select(SalesOrderItemModel).where(SalesOrderItemModel.client_id == client_id, SalesOrderItemModel.order_id == sale_id)
            ).scalars().all()
            returned = session.execute(
                select(SalesReturnItemModel.sale_item_id, SalesReturnItemModel.return_qty).where(
                    SalesReturnItemModel.client_id == client_id,
                    SalesReturnItemModel.sale_item_id.in_([item.order_item_id for item in items] or ["__none__"]),
                )
            ).all()

        returned_map: dict[str, float] = defaultdict(float)
        for sale_item_id, qty in returned:
            returned_map[str(sale_item_id)] += self._to_float(qty)

        lines = []
        for item in items:
            sold_qty = self._to_float(item.qty)
            already_returned = returned_map.get(item.order_item_id, 0.0)
            remaining = max(0.0, sold_qty - already_returned)
            lines.append(
                {
                    "sale_item_id": item.order_item_id,
                    "product_id": item.product_id,
                    "variant_id": item.variant_id,
                    "product_name": item.product_name_snapshot,
                    "sold_qty": sold_qty,
                    "already_returned_qty": already_returned,
                    "eligible_qty": remaining,
                    "unit_price": self._to_float(item.unit_selling_price),
                }
            )

        return {
            "sale_id": order.order_id,
            "sale_no": order.sale_no,
            "customer_id": order.customer_id,
            "customer_name": customer.full_name if customer else "",
            "sale_date": order.timestamp,
            "lines": lines,
        }

    def get_return_detail(self, *, client_id: str, return_id: str) -> dict[str, object] | None:
        with self.session_factory() as session:
            ret = session.execute(
                select(SalesReturnModel).where(SalesReturnModel.client_id == client_id, SalesReturnModel.return_id == return_id)
            ).scalar_one_or_none()
            if ret is None:
                return None
            customer = session.execute(
                select(CustomerModel).where(CustomerModel.client_id == client_id, CustomerModel.customer_id == ret.customer_id)
            ).scalar_one_or_none()
            lines = session.execute(
                select(SalesReturnItemModel).where(
                    SalesReturnItemModel.client_id == client_id,
                    SalesReturnItemModel.return_id == return_id,
                )
            ).scalars().all()
        return {
            "return_id": ret.return_id,
            "return_no": ret.return_no,
            "sale_id": ret.sale_id,
            "sale_no": ret.sale_no,
            "customer_id": ret.customer_id,
            "customer_name": customer.full_name if customer else "",
            "reason": ret.reason,
            "note": ret.note,
            "return_total": self._to_float(ret.return_total),
            "created_at": ret.created_at,
            "lines": [
                {
                    "return_item_id": line.return_item_id,
                    "sale_item_id": line.sale_item_id,
                    "product_id": line.product_id,
                    "variant_id": line.variant_id,
                    "product_name": line.product_name_snapshot,
                    "sold_qty": self._to_float(line.sold_qty),
                    "return_qty": self._to_float(line.return_qty),
                    "unit_price": self._to_float(line.unit_price),
                    "line_total": self._to_float(line.line_total),
                    "reason": line.reason,
                    "condition_status": line.condition_status,
                }
                for line in lines
            ],
        }

    def create_return(self, *, client_id: str, user_id: str, payload: ReturnCreateInput) -> dict[str, object]:
        if not payload.lines:
            raise ValueError("At least one return line is required")
        if not payload.reason.strip():
            raise ValueError("reason is required")

        return_id = new_uuid()
        return_no = f"RET-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{return_id[:6].upper()}"

        with self.session_factory() as session:
            order = session.execute(
                select(SalesOrderModel).where(
                    SalesOrderModel.client_id == client_id,
                    SalesOrderModel.order_id == payload.sale_id,
                )
            ).scalar_one_or_none()
            if order is None:
                raise ValueError("Invalid sale for tenant")

            sale_items = session.execute(
                select(SalesOrderItemModel).where(
                    SalesOrderItemModel.client_id == client_id,
                    SalesOrderItemModel.order_id == payload.sale_id,
                )
            ).scalars().all()
            by_item_id = {item.order_item_id: item for item in sale_items}

            requested_by_item: dict[str, float] = defaultdict(float)
            for line in payload.lines:
                if line.qty <= 0:
                    raise ValueError("Return quantity must be > 0")
                if line.sale_item_id not in by_item_id:
                    raise ValueError(f"Invalid sale line reference: {line.sale_item_id}")
                requested_by_item[line.sale_item_id] += line.qty

            prior_returns = session.execute(
                select(SalesReturnItemModel.sale_item_id, SalesReturnItemModel.return_qty).where(
                    SalesReturnItemModel.client_id == client_id,
                    SalesReturnItemModel.sale_item_id.in_(list(requested_by_item.keys()) or ["__none__"]),
                )
            ).all()
            prior_by_item: dict[str, float] = defaultdict(float)
            for sale_item_id, qty in prior_returns:
                prior_by_item[str(sale_item_id)] += self._to_float(qty)

            for sale_item_id, requested_qty in requested_by_item.items():
                sold_qty = self._to_float(by_item_id[sale_item_id].qty)
                eligible = max(0.0, sold_qty - prior_by_item.get(sale_item_id, 0.0))
                if requested_qty > eligible:
                    raise ValueError(f"Return quantity exceeds eligible quantity for line {sale_item_id}")

            return_total = 0.0
            return_items: list[SalesReturnItemModel] = []
            for line in payload.lines:
                sale_item = by_item_id[line.sale_item_id]
                unit_price = self._to_float(sale_item.unit_selling_price)
                line_total = unit_price * float(line.qty)
                return_total += line_total
                return_items.append(
                    SalesReturnItemModel(
                        return_item_id=new_uuid(),
                        return_id=return_id,
                        client_id=client_id,
                        sale_item_id=sale_item.order_item_id,
                        product_id=sale_item.product_id,
                        variant_id=sale_item.variant_id,
                        product_name_snapshot=sale_item.product_name_snapshot,
                        sold_qty=str(self._to_float(sale_item.qty)),
                        return_qty=str(float(line.qty)),
                        unit_price=str(unit_price),
                        line_total=str(line_total),
                        reason=line.reason.strip() or payload.reason.strip(),
                        condition_status=line.condition_status.strip(),
                    )
                )

            sale_total = self._to_float(order.grand_total)
            amount_paid = self._to_float(order.amount_paid)
            new_sale_total = max(0.0, sale_total - return_total)
            new_outstanding = max(0.0, new_sale_total - amount_paid)
            if new_outstanding == 0 and new_sale_total == 0:
                payment_status = "paid"
            elif new_outstanding == 0:
                payment_status = "paid"
            elif amount_paid > 0:
                payment_status = "partial"
            else:
                payment_status = "unpaid"

            sale_no = order.sale_no

            session.add(
                SalesReturnModel(
                    return_id=return_id,
                    client_id=client_id,
                    return_no=return_no,
                    sale_id=order.order_id,
                    sale_no=sale_no,
                    customer_id=order.customer_id,
                    reason=payload.reason.strip(),
                    note=payload.note.strip(),
                    return_total=str(return_total),
                    created_at=now_iso(),
                    created_by_user_id=user_id,
                )
            )
            session.add_all(return_items)

            for line in return_items:
                session.add(
                    InventoryTxnModel(
                        txn_id=new_uuid(),
                        client_id=client_id,
                        timestamp=now_iso(),
                        user_id=user_id,
                        txn_type="IN",
                        product_id=line.product_id,
                        variant_id=line.variant_id,
                        product_name=line.product_name_snapshot,
                        qty=line.return_qty,
                        unit_cost=line.unit_price,
                        total_cost=line.line_total,
                        supplier_snapshot="",
                        note=f"return:{return_no}",
                        source_type="sale_return",
                        source_id=return_id,
                        lot_id="",
                    )
                )

            order.grand_total = str(new_sale_total)
            order.outstanding_balance = str(new_outstanding)
            order.payment_status = payment_status
            order.note = f"{order.note} | return:{return_no}".strip(" |")
            session.commit()

        return {
            "return_id": return_id,
            "return_no": return_no,
            "sale_id": payload.sale_id,
            "sale_no": sale_no,
            "return_total": return_total,
        }
