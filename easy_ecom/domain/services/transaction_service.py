from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import ColumnElement, func, literal, select, true, union_all
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.api.schemas.finance import FinanceTransaction
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.store.postgres_models import AuditLogModel, ExpenseModel, PaymentModel
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

    def _normalize_payment_status(self, value: object | None, default: str = "completed") -> str:
        status = self._normalize_text(value, default=default).lower()
        if status not in {"paid", "unpaid", "partial", "completed", "pending", "succeeded"}:
            raise ValueError("Unsupported payment status")
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

    def _payment_to_transaction(self, payment: PaymentModel) -> FinanceTransaction:
        entry_date = payment.paid_at or payment.created_at
        direction = payment.direction or ("out" if payment.sales_return_id else "in")
        return FinanceTransaction(
            entry_id=str(payment.payment_id),
            entry_date=entry_date.isoformat(),
            entry_type="payment",
            direction=direction,
            category=payment.method,
            amount=float(payment.amount),
            reference=payment.reference,
            note=payment.notes,
            payment_status=payment.status,
            vendor_name=None,
        )

    def _expense_to_transaction(self, expense: ExpenseModel) -> FinanceTransaction:
        return FinanceTransaction(
            entry_id=str(expense.expense_id),
            entry_date=expense.incurred_at.isoformat(),
            entry_type="expense",
            direction="out",
            category=expense.category,
            amount=float(expense.amount),
            reference=expense.expense_number,
            note=expense.description,
            payment_status=expense.payment_status,
            vendor_name=expense.vendor_name,
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

    def _payment_query(self, context: TransactionContext):
        return select(PaymentModel).where(self._tenant_filter(context, PaymentModel))

    def _expense_query(self, context: TransactionContext):
        return select(ExpenseModel).where(self._tenant_filter(context, ExpenseModel))

    def get_transactions(
        self,
        context: TransactionContext,
        limit: int = 100,
        offset: int = 0,
        transaction_type: Optional[str] = None,
    ) -> List[dict]:
        with self._session_factory() as session:
            payment_event = func.coalesce(PaymentModel.paid_at, PaymentModel.created_at)
            expense_event = ExpenseModel.incurred_at

            payment_select = select(
                payment_event.label("sort_date"),
                literal("payment").label("entry_type"),
                PaymentModel.payment_id.label("entry_id"),
                payment_event.label("entry_date"),
                PaymentModel.direction.label("direction"),
                PaymentModel.method.label("category"),
                PaymentModel.amount.label("amount"),
                PaymentModel.reference.label("reference"),
                PaymentModel.notes.label("note"),
                PaymentModel.status.label("payment_status"),
                literal(None).label("vendor_name"),
            ).where(self._tenant_filter(context, PaymentModel))

            expense_select = select(
                expense_event.label("sort_date"),
                literal("expense").label("entry_type"),
                ExpenseModel.expense_id.label("entry_id"),
                expense_event.label("entry_date"),
                literal("out").label("direction"),
                ExpenseModel.category.label("category"),
                ExpenseModel.amount.label("amount"),
                ExpenseModel.expense_number.label("reference"),
                ExpenseModel.description.label("note"),
                ExpenseModel.payment_status.label("payment_status"),
                ExpenseModel.vendor_name.label("vendor_name"),
            ).where(self._tenant_filter(context, ExpenseModel))

            if transaction_type == "payment":
                combined = payment_select
            elif transaction_type == "expense":
                combined = expense_select
            else:
                combined = union_all(payment_select, expense_select)

            journal_source = combined.subquery()
            journal = select(journal_source).order_by(
                journal_source.c.sort_date.desc(),
                journal_source.c.entry_id.desc(),
            )
            rows = session.execute(journal.offset(offset).limit(limit)).mappings().all()
            transactions: list[FinanceTransaction] = []
            for row in rows:
                transactions.append(
                    FinanceTransaction(
                        entry_id=str(row["entry_id"]),
                        entry_date=row["entry_date"].isoformat() if hasattr(row["entry_date"], "isoformat") else str(row["entry_date"]),
                        entry_type=str(row["entry_type"]),
                        direction=str(row["direction"]),
                        category=str(row["category"]),
                        amount=float(row["amount"]),
                        reference=str(row["reference"] or ""),
                        note=str(row["note"] or ""),
                        payment_status=str(row["payment_status"]) if row["payment_status"] is not None else None,
                        vendor_name=str(row["vendor_name"]) if row["vendor_name"] is not None else None,
                    )
                )
            return [transaction.model_dump() for transaction in transactions]

    def count_transactions(
        self,
        context: TransactionContext,
        transaction_type: Optional[str] = None,
    ) -> int:
        with self._session_factory() as session:
            total = 0
            if transaction_type in [None, "payment"]:
                total += int(
                    session.execute(
                        select(func.count()).select_from(PaymentModel).where(self._tenant_filter(context, PaymentModel))
                    ).scalar_one()
                    or 0
                )
            if transaction_type in [None, "expense"]:
                total += int(
                    session.execute(
                        select(func.count()).select_from(ExpenseModel).where(self._tenant_filter(context, ExpenseModel))
                    ).scalar_one()
                    or 0
                )
            return total

    def get_transaction(
        self,
        context: TransactionContext,
        transaction_id: str,
    ) -> Optional[dict]:
        with self._session_factory() as session:
            payment = session.execute(
                self._payment_query(context).where(PaymentModel.payment_id == transaction_id)
            ).scalar_one_or_none()
            if payment is not None:
                return self._payment_to_transaction(payment).model_dump()

            expense = session.execute(
                self._expense_query(context).where(ExpenseModel.expense_id == transaction_id)
            ).scalar_one_or_none()
            if expense is not None:
                return self._expense_to_transaction(expense).model_dump()

            return None

    def create_transaction(
        self,
        context: TransactionContext,
        transaction_type: str,
        data: dict,
    ) -> dict:
        with self._session_factory() as session:
            if transaction_type == "payment":
                payment = PaymentModel(
                    payment_id=new_uuid(),
                    client_id=context.user.client_id,
                    amount=self._normalize_amount(data.get("amount")),
                    method=self._normalize_text(data.get("category"), default="manual"),
                    direction=self._normalize_direction(data.get("direction"), default="in"),
                    reference=self._normalize_text(data.get("reference")),
                    notes=self._normalize_text(data.get("note")),
                    status=self._normalize_payment_status(data.get("payment_status"), default="completed"),
                    paid_at=self._parse_datetime(data.get("entry_date")),
                    created_by_user_id=context.user.user_id,
                )
                session.add(payment)
                self._log_audit(
                    session,
                    context=context,
                    entity_type="finance_transaction",
                    entity_id=payment.payment_id,
                    action="payment_created",
                    metadata_json={
                        "entry_type": "payment",
                        "direction": payment.direction,
                        "category": payment.method,
                        "amount": float(payment.amount),
                    },
                )
                session.commit()
                session.refresh(payment)
                return self._payment_to_transaction(payment).model_dump()

            if transaction_type == "expense":
                expense = ExpenseModel(
                    expense_id=new_uuid(),
                    client_id=context.user.client_id,
                    amount=self._normalize_amount(data.get("amount")),
                    category=self._normalize_text(data.get("category"), default="general"),
                    description=self._normalize_text(data.get("note")),
                    vendor_name=self._normalize_text(data.get("vendor_name")),
                    expense_number=self._normalize_text(data.get("reference")),
                    incurred_at=self._parse_datetime(data.get("entry_date")),
                    payment_status=self._normalize_payment_status(data.get("payment_status"), default="unpaid"),
                    created_by_user_id=context.user.user_id,
                )
                session.add(expense)
                self._log_audit(
                    session,
                    context=context,
                    entity_type="finance_transaction",
                    entity_id=expense.expense_id,
                    action="expense_created",
                    metadata_json={
                        "entry_type": "expense",
                        "category": expense.category,
                        "vendor_name": expense.vendor_name,
                        "amount": float(expense.amount),
                    },
                )
                session.commit()
                session.refresh(expense)
                return self._expense_to_transaction(expense).model_dump()

            raise ValueError(f"Unsupported transaction type: {transaction_type}")

    def update_transaction(
        self,
        context: TransactionContext,
        transaction_id: str,
        transaction_type: str,
        data: dict,
    ) -> dict:
        with self._session_factory() as session:
            changed_fields: list[str] = []

            if transaction_type == "payment":
                payment = session.execute(
                    self._payment_query(context).where(PaymentModel.payment_id == transaction_id)
                ).scalar_one_or_none()
                if payment is None:
                    raise ValueError("Payment not found or not authorized")

                if "amount" in data:
                    payment.amount = self._normalize_amount(data.get("amount"))
                    changed_fields.append("amount")
                if "category" in data and data.get("category") is not None:
                    payment.method = self._normalize_text(data.get("category"), default=payment.method)
                    changed_fields.append("category")
                if "reference" in data and data.get("reference") is not None:
                    payment.reference = self._normalize_text(data.get("reference"))
                    changed_fields.append("reference")
                if "note" in data and data.get("note") is not None:
                    payment.notes = self._normalize_text(data.get("note"))
                    changed_fields.append("note")
                if "entry_date" in data and data.get("entry_date") is not None:
                    payment.paid_at = self._parse_datetime(data.get("entry_date"))
                    changed_fields.append("entry_date")
                if "direction" in data and data.get("direction") is not None:
                    requested_direction = self._normalize_direction(data.get("direction"), default=payment.direction)
                    if payment.sales_return_id is not None and requested_direction != "out":
                        raise ValueError("Refund-linked payments remain outgoing cash entries")
                    payment.direction = requested_direction
                    changed_fields.append("direction")
                if "payment_status" in data and data.get("payment_status") is not None:
                    payment.status = self._normalize_payment_status(data.get("payment_status"), default=payment.status)
                    changed_fields.append("payment_status")

                self._log_audit(
                    session,
                    context=context,
                    entity_type="finance_transaction",
                    entity_id=payment.payment_id,
                    action="payment_updated",
                    metadata_json={"changed_fields": changed_fields},
                )
                session.commit()
                session.refresh(payment)
                return self._payment_to_transaction(payment).model_dump()

            if transaction_type == "expense":
                expense = session.execute(
                    self._expense_query(context).where(ExpenseModel.expense_id == transaction_id)
                ).scalar_one_or_none()
                if expense is None:
                    raise ValueError("Expense not found or not authorized")

                if "amount" in data and data.get("amount") is not None:
                    expense.amount = self._normalize_amount(data.get("amount"))
                    changed_fields.append("amount")
                if "category" in data and data.get("category") is not None:
                    expense.category = self._normalize_text(data.get("category"), default=expense.category)
                    changed_fields.append("category")
                if "note" in data and data.get("note") is not None:
                    expense.description = self._normalize_text(data.get("note"))
                    changed_fields.append("note")
                if "vendor_name" in data and data.get("vendor_name") is not None:
                    expense.vendor_name = self._normalize_text(data.get("vendor_name"))
                    changed_fields.append("vendor_name")
                if "reference" in data and data.get("reference") is not None:
                    expense.expense_number = self._normalize_text(data.get("reference"))
                    changed_fields.append("reference")
                if "entry_date" in data and data.get("entry_date") is not None:
                    expense.incurred_at = self._parse_datetime(data.get("entry_date"))
                    changed_fields.append("entry_date")
                if "payment_status" in data and data.get("payment_status") is not None:
                    expense.payment_status = self._normalize_payment_status(data.get("payment_status"), default=expense.payment_status)
                    changed_fields.append("payment_status")

                self._log_audit(
                    session,
                    context=context,
                    entity_type="finance_transaction",
                    entity_id=expense.expense_id,
                    action="expense_updated",
                    metadata_json={"changed_fields": changed_fields},
                )
                session.commit()
                session.refresh(expense)
                return self._expense_to_transaction(expense).model_dump()

            raise ValueError(f"Unsupported transaction type: {transaction_type}")
