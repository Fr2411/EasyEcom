from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import ColumnElement, func, select, true
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.api.schemas.finance import FinanceTransaction
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.store.postgres_models import AuditLogModel, ClientModel, FinanceTransactionModel
from easy_ecom.domain.models.auth import AuthenticatedUser


@dataclass(frozen=True)
class TransactionContext:
    user: AuthenticatedUser

    @property
    def is_super_admin(self) -> bool:
        return "SUPER_ADMIN" in self.user.roles


class TransactionService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _tenant_filter(self, context: TransactionContext, model) -> ColumnElement[bool]:
        if context.is_super_admin:
            return true()
        return model.client_id == context.user.client_id

    def _normalize_text(self, value: object | None, default: str = "") -> str:
        if value is None:
            return default
        return str(value).strip() or default

    def _normalize_amount(self, value: object | None) -> Decimal:
        if value is None or value == "":
            return Decimal("0")
        return Decimal(str(value))

    def _normalize_direction(self, value: object | None, default: str = "in") -> str:
        direction = self._normalize_text(value, default=default).lower()
        if direction not in {"in", "out"}:
            raise ValueError("direction must be either 'in' or 'out'")
        return direction

    def _normalize_status(self, value: object | None, default: str = "completed") -> str:
        status = self._normalize_text(value, default=default).lower()
        if status not in {"paid", "unpaid", "partial", "completed", "pending", "posted", "reversed"}:
            raise ValueError("Unsupported finance status")
        return status

    def _parse_datetime(self, value: object | None) -> datetime:
        if value in (None, ""):
            return now_utc()
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=now_utc().tzinfo)
        text = self._normalize_text(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=now_utc().tzinfo)

    def _currency_code(self, session: Session, client_id: str) -> str:
        value = session.execute(
            select(ClientModel.currency_code).where(ClientModel.client_id == client_id)
        ).scalar_one_or_none()
        return str(value or "USD")

    def _transaction_to_schema(self, transaction: FinanceTransactionModel) -> FinanceTransaction:
        source_label = {
            "sale_fulfillment": "From Sales",
            "return_refund": "From Returns",
            "manual_payment": "Manual payment",
            "manual_expense": "Manual expense",
        }.get(transaction.origin_type, transaction.origin_type.replace("_", " ").title())
        return FinanceTransaction(
            transaction_id=str(transaction.transaction_id),
            origin_type=str(transaction.origin_type),
            origin_id=str(transaction.origin_id) if transaction.origin_id else None,
            occurred_at=transaction.occurred_at.isoformat(),
            direction=str(transaction.direction),
            status=str(transaction.status),
            amount=float(transaction.amount),
            currency_code=transaction.currency_code,
            reference=transaction.reference,
            note=transaction.note,
            counterparty_type=str(transaction.counterparty_type) if transaction.counterparty_type else None,
            counterparty_id=str(transaction.counterparty_id) if transaction.counterparty_id else None,
            counterparty_name=transaction.counterparty_name,
            editable=str(transaction.origin_type).startswith("manual_"),
            source_label=source_label,
        )

    def _log_audit(
        self,
        session: Session,
        *,
        context: TransactionContext,
        entity_type: str,
        entity_id: str,
        action: str,
        metadata_json: dict[str, object] | None,
    ) -> None:
        session.add(
            AuditLogModel(
                audit_log_id=new_uuid(),
                client_id=context.user.client_id,
                actor_user_id=context.user.user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                request_id=None,
                metadata_json=metadata_json,
                created_at=now_utc(),
            )
        )

    def _transaction_query(self, context: TransactionContext):
        return select(FinanceTransactionModel).where(self._tenant_filter(context, FinanceTransactionModel))

    def get_transactions(
        self,
        context: TransactionContext,
        limit: int = 100,
        offset: int = 0,
        transaction_type: Optional[str] = None,
    ) -> List[dict]:
        with self._session_factory() as session:
            stmt = self._transaction_query(context)
            if transaction_type is not None:
                stmt = stmt.where(FinanceTransactionModel.origin_type == transaction_type)
            rows = session.execute(
                stmt.order_by(
                    FinanceTransactionModel.occurred_at.desc(),
                    FinanceTransactionModel.transaction_id.desc(),
                ).offset(offset).limit(limit)
            ).scalars().all()
            return [self._transaction_to_schema(transaction).model_dump() for transaction in rows]

    def count_transactions(
        self,
        context: TransactionContext,
        transaction_type: Optional[str] = None,
    ) -> int:
        with self._session_factory() as session:
            stmt = select(func.count()).select_from(FinanceTransactionModel).where(self._tenant_filter(context, FinanceTransactionModel))
            if transaction_type is not None:
                stmt = stmt.where(FinanceTransactionModel.origin_type == transaction_type)
            return int(session.execute(stmt).scalar_one() or 0)

    def get_transaction(
        self,
        context: TransactionContext,
        transaction_id: str,
    ) -> Optional[dict]:
        with self._session_factory() as session:
            transaction = session.execute(
                self._transaction_query(context).where(FinanceTransactionModel.transaction_id == transaction_id)
            ).scalar_one_or_none()
            return self._transaction_to_schema(transaction).model_dump() if transaction is not None else None

    def create_transaction(
        self,
        context: TransactionContext,
        transaction_type: str,
        data: dict,
    ) -> dict:
        with self._session_factory() as session:
            if transaction_type not in {"manual_payment", "manual_expense"}:
                raise ValueError(f"Unsupported manual transaction type: {transaction_type}")
            transaction = FinanceTransactionModel(
                transaction_id=new_uuid(),
                client_id=context.user.client_id,
                origin_type=transaction_type,
                origin_id=None,
                amount=self._normalize_amount(data.get("amount")),
                direction=self._normalize_direction(
                    data.get("direction"),
                    default="in" if transaction_type == "manual_payment" else "out",
                ),
                status=self._normalize_status(
                    data.get("status"),
                    default="completed" if transaction_type == "manual_payment" else "unpaid",
                ),
                occurred_at=self._parse_datetime(data.get("occurred_at")),
                currency_code=self._normalize_text(
                    data.get("currency_code"),
                    default=self._currency_code(session, context.user.client_id),
                ).upper(),
                reference=self._normalize_text(data.get("reference")),
                note=self._normalize_text(data.get("note")),
                counterparty_type=self._normalize_text(data.get("counterparty_type")) or None,
                counterparty_name=self._normalize_text(data.get("counterparty_name")),
                created_by_user_id=context.user.user_id,
            )
            session.add(transaction)
            self._log_audit(
                session,
                context=context,
                entity_type="finance_transaction",
                entity_id=transaction.transaction_id,
                action="manual_finance_transaction_created",
                metadata_json={
                    "origin_type": transaction.origin_type,
                    "direction": transaction.direction,
                    "amount": float(transaction.amount),
                },
            )
            session.commit()
            session.refresh(transaction)
            return self._transaction_to_schema(transaction).model_dump()

    def update_transaction(
        self,
        context: TransactionContext,
        transaction_id: str,
        transaction_type: str,
        data: dict,
    ) -> dict:
        with self._session_factory() as session:
            changed_fields: list[str] = []

            transaction = session.execute(
                self._transaction_query(context).where(FinanceTransactionModel.transaction_id == transaction_id)
            ).scalar_one_or_none()
            if transaction is None:
                raise ValueError("Transaction not found or not authorized")
            if transaction.origin_type not in {"manual_payment", "manual_expense"}:
                raise ValueError("Only manual finance transactions can be edited from Finance")
            if transaction_type != transaction.origin_type:
                raise ValueError("origin_type cannot be changed")

            if "amount" in data and data.get("amount") is not None:
                transaction.amount = self._normalize_amount(data.get("amount"))
                changed_fields.append("amount")
            if "reference" in data and data.get("reference") is not None:
                transaction.reference = self._normalize_text(data.get("reference"))
                changed_fields.append("reference")
            if "note" in data and data.get("note") is not None:
                transaction.note = self._normalize_text(data.get("note"))
                changed_fields.append("note")
            if "occurred_at" in data and data.get("occurred_at") is not None:
                transaction.occurred_at = self._parse_datetime(data.get("occurred_at"))
                changed_fields.append("occurred_at")
            if "direction" in data and data.get("direction") is not None:
                transaction.direction = self._normalize_direction(data.get("direction"), default=transaction.direction)
                changed_fields.append("direction")
            if "status" in data and data.get("status") is not None:
                transaction.status = self._normalize_status(data.get("status"), default=transaction.status)
                changed_fields.append("status")
            if "currency_code" in data and data.get("currency_code") is not None:
                transaction.currency_code = self._normalize_text(data.get("currency_code"), default=transaction.currency_code).upper()
                changed_fields.append("currency_code")
            if "counterparty_type" in data and data.get("counterparty_type") is not None:
                transaction.counterparty_type = self._normalize_text(data.get("counterparty_type")) or None
                changed_fields.append("counterparty_type")
            if "counterparty_name" in data and data.get("counterparty_name") is not None:
                transaction.counterparty_name = self._normalize_text(data.get("counterparty_name"))
                changed_fields.append("counterparty_name")

            self._log_audit(
                session,
                context=context,
                entity_type="finance_transaction",
                entity_id=transaction.transaction_id,
                action="manual_finance_transaction_updated",
                metadata_json={"changed_fields": changed_fields},
            )
            session.commit()
            session.refresh(transaction)
            return self._transaction_to_schema(transaction).model_dump()
