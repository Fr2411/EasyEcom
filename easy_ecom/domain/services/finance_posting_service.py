from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.store.postgres_models import (
    AuditLogModel,
    ClientModel,
    FinanceTransactionLinkModel,
    FinanceTransactionModel,
    RefundModel,
    SalesOrderModel,
    SalesReturnModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser

ZERO = Decimal("0")


@dataclass(frozen=True)
class FinancePostResult:
    transaction_id: str
    occurred_at: datetime
    amount: Decimal
    origin_type: str


class FinancePostingService:
    def _currency_code(self, session: Session, client_id: str) -> str:
        return str(
            session.execute(
                select(ClientModel.currency_code).where(ClientModel.client_id == client_id)
            ).scalar_one_or_none()
            or "USD"
        )

    def _log_audit(
        self,
        session: Session,
        *,
        user: AuthenticatedUser,
        entity_id: str,
        action: str,
        metadata_json: dict[str, object] | None,
    ) -> None:
        session.add(
            AuditLogModel(
                audit_log_id=new_uuid(),
                client_id=user.client_id,
                actor_user_id=user.user_id,
                entity_type="finance_transaction",
                entity_id=entity_id,
                action=action,
                request_id=None,
                metadata_json=metadata_json,
                created_at=now_utc(),
            )
        )

    def _link_exists(self, session: Session, *, client_id: str, origin_type: str, origin_id: str) -> bool:
        return bool(
            session.execute(
                select(FinanceTransactionLinkModel.finance_transaction_link_id).where(
                    FinanceTransactionLinkModel.client_id == client_id,
                    FinanceTransactionLinkModel.origin_type == origin_type,
                    FinanceTransactionLinkModel.origin_id == origin_id,
                )
            ).scalar_one_or_none()
        )

    def _create_transaction(
        self,
        session: Session,
        *,
        user: AuthenticatedUser,
        origin_type: str,
        origin_id: str | None,
        direction: str,
        status: str,
        occurred_at: datetime,
        amount: Decimal,
        reference: str,
        note: str,
        counterparty_type: str | None,
        counterparty_id: str | None,
        counterparty_name: str,
    ) -> FinanceTransactionModel:
        transaction = FinanceTransactionModel(
            transaction_id=new_uuid(),
            client_id=user.client_id,
            origin_type=origin_type,
            origin_id=origin_id,
            direction=direction,
            status=status,
            occurred_at=occurred_at,
            amount=amount,
            currency_code=self._currency_code(session, user.client_id),
            reference=reference.strip(),
            note=note.strip(),
            counterparty_type=counterparty_type,
            counterparty_id=counterparty_id,
            counterparty_name=counterparty_name.strip(),
            created_by_user_id=user.user_id,
        )
        session.add(transaction)
        session.flush()
        if origin_id is not None:
            session.add(
                FinanceTransactionLinkModel(
                    finance_transaction_link_id=new_uuid(),
                    client_id=user.client_id,
                    transaction_id=transaction.transaction_id,
                    origin_type=origin_type,
                    origin_id=origin_id,
                )
            )
        return transaction

    def post_sale_fulfillment(
        self,
        session: Session,
        *,
        user: AuthenticatedUser,
        order: SalesOrderModel,
        customer_name: str,
    ) -> FinancePostResult | None:
        origin_id = str(order.sales_order_id)
        if self._link_exists(session, client_id=user.client_id, origin_type="sale_fulfillment", origin_id=origin_id):
            return None
        transaction = self._create_transaction(
            session,
            user=user,
            origin_type="sale_fulfillment",
            origin_id=origin_id,
            direction="in",
            status="posted",
            occurred_at=now_utc(),
            amount=Decimal(str(order.total_amount or ZERO)),
            reference=order.order_number,
            note=order.notes or "Recognized on order fulfillment",
            counterparty_type="customer",
            counterparty_id=str(order.customer_id) if order.customer_id else None,
            counterparty_name=customer_name,
        )
        self._log_audit(
            session,
            user=user,
            entity_id=transaction.transaction_id,
            action="sale_fulfillment_posted",
            metadata_json={"sales_order_id": origin_id, "amount": float(transaction.amount)},
        )
        return FinancePostResult(
            transaction_id=str(transaction.transaction_id),
            occurred_at=transaction.occurred_at,
            amount=Decimal(str(transaction.amount)),
            origin_type="sale_fulfillment",
        )

    def record_return_refund(
        self,
        session: Session,
        *,
        user: AuthenticatedUser,
        return_record: SalesReturnModel,
        customer_name: str,
        amount: Decimal,
        occurred_at: datetime,
        method: str,
        reference: str,
        note: str,
    ) -> FinancePostResult:
        transaction = self._create_transaction(
            session,
            user=user,
            origin_type="return_refund",
            origin_id=str(return_record.sales_return_id),
            direction="out",
            status="posted",
            occurred_at=occurred_at,
            amount=amount,
            reference=reference.strip() or return_record.return_number,
            note=note.strip() or f"Refund paid via {method.strip() or 'manual'}",
            counterparty_type="customer",
            counterparty_id=str(return_record.customer_id) if return_record.customer_id else None,
            counterparty_name=customer_name,
        )
        session.add(
            RefundModel(
                refund_id=new_uuid(),
                client_id=user.client_id,
                sales_return_id=return_record.sales_return_id,
                payment_id=None,
                status="completed",
                amount=amount,
                refunded_at=occurred_at,
                reason=note.strip() or f"Refund paid via {method.strip() or 'manual'}",
                created_by_user_id=user.user_id,
            )
        )
        self._log_audit(
            session,
            user=user,
            entity_id=transaction.transaction_id,
            action="return_refund_posted",
            metadata_json={"sales_return_id": str(return_record.sales_return_id), "amount": float(amount)},
        )
        return FinancePostResult(
            transaction_id=str(transaction.transaction_id),
            occurred_at=transaction.occurred_at,
            amount=Decimal(str(transaction.amount)),
            origin_type="return_refund",
        )

    def refunded_total(self, session: Session, *, client_id: str, sales_return_id: str) -> Decimal:
        value = session.execute(
            select(func.coalesce(func.sum(FinanceTransactionModel.amount), 0)).where(
                FinanceTransactionModel.client_id == client_id,
                FinanceTransactionModel.origin_type == "return_refund",
                FinanceTransactionModel.origin_id == sales_return_id,
            )
        ).scalar_one()
        return Decimal(str(value or ZERO))
