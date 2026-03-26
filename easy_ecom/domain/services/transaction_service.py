from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Union
from uuid import UUID

from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.data.store.postgres_models import (
    PaymentModel,
    ExpenseModel,
)
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

    def _get_payment_filters(self, context: TransactionContext):
        filters = []
        if not context.is_super_admin:
            filters.append(PaymentModel.client_id == context.user.client_id)
        return and_(*filters) if filters else True

    def _get_expense_filters(self, context: TransactionContext):
        filters = []
        if not context.is_super_admin:
            filters.append(ExpenseModel.client_id == context.user.client_id)
        return and_(*filters) if filters else True

    def _payment_to_transaction(self, payment: PaymentModel) -> dict:
        return {
            "entry_id": str(payment.payment_id),
            "entry_date": payment.paid_at.isoformat() if payment.paid_at else payment.created_at.isoformat(),
            "entry_type": "payment",
            "category": payment.method,
            "amount": float(payment.amount),
            "direction": "in",  # Assuming all payments are incoming (received from customers)
            "reference": payment.reference,
            "note": payment.notes,
        }

    def _expense_to_transaction(self, expense: ExpenseModel) -> dict:
        return {
            "entry_id": str(expense.expense_id),
            "entry_date": expense.incurred_at.isoformat(),
            "entry_type": "expense",
            "category": expense.category,
            "amount": float(expense.amount),
            "direction": "out",  # Expenses are outgoing
            "reference": expense.expense_number,
            "note": expense.description,
        }

    def get_transactions(
        self,
        context: TransactionContext,
        limit: int = 100,
        offset: int = 0,
        transaction_type: Optional[str] = None,
    ) -> List[dict]:
        with self._session_factory() as session:
            transactions = []

            if transaction_type in [None, "payment"]:
                payment_stmt = select(PaymentModel).where(
                    self._get_payment_filters(context)
                ).offset(offset).limit(limit)
                payments = session.execute(payment_stmt).scalars().all()
                for payment in payments:
                    transactions.append(self._payment_to_transaction(payment))

            if transaction_type in [None, "expense"]:
                expense_stmt = select(ExpenseModel).where(
                    self._get_expense_filters(context)
                ).offset(offset).limit(limit)
                expenses = session.execute(expense_stmt).scalars().all()
                for expense in expenses:
                    transactions.append(self._expense_to_transaction(expense))

            # Sort by entry_date descending
            transactions.sort(key=lambda x: x["entry_date"], reverse=True)
            return transactions[offset:offset+limit]

    def get_transaction(
        self,
        context: TransactionContext,
        transaction_id: str
    ) -> Optional[dict]:
        with self._session_factory() as session:
            # Try to find as payment first
            payment = session.get(PaymentModel, transaction_id)
            if payment and (
                context.is_super_admin or 
                payment.client_id == context.user.client_id
            ):
                return self._payment_to_transaction(payment)

            # Then try as expense
            expense = session.get(ExpenseModel, transaction_id)
            if expense and (
                context.is_super_admin or 
                expense.client_id == context.user.client_id
            ):
                return self._expense_to_transaction(expense)

            return None

    def create_transaction(
        self,
        context: TransactionContext,
        transaction_type: str,
        data: dict
    ) -> dict:
        with self._session_factory() as session:
            if transaction_type == "payment":
                payment = PaymentModel(
                    client_id=context.user.client_id,
                    amount=data.get("amount", 0),
                    method=data.get("category", "manual"),  # Using category as method
                    reference=data.get("reference", ""),
                    notes=data.get("note", ""),
                    status="completed",  # Assuming immediate completion
                    paid_at=data.get("entry_date"),  # entry_date should be a datetime string
                    created_by_user_id=context.user.user_id,
                )
                session.add(payment)
                session.commit()
                session.refresh(payment)
                return self._payment_to_transaction(payment)

            elif transaction_type == "expense":
                expense = ExpenseModel(
                    client_id=context.user.client_id,
                    amount=data.get("amount", 0),
                    category=data.get("category", "general"),
                    description=data.get("note", ""),
                    vendor_name=data.get("vendor_name", ""),
                    expense_number=data.get("reference", ""),  # Using reference as expense_number
                    incurred_at=data.get("entry_date"),  # entry_date should be a datetime string
                    payment_status="paid" if data.get("direction") == "in" else "unpaid",
                    created_by_user_id=context.user.user_id,
                )
                session.add(expense)
                session.commit()
                session.refresh(expense)
                return self._expense_to_transaction(expense)

            else:
                raise ValueError(f"Unsupported transaction type: {transaction_type}")

    def update_transaction(
        self,
        context: TransactionContext,
        transaction_id: str,
        transaction_type: str,
        data: dict
    ) -> dict:
        with self._session_factory() as session:
            if transaction_type == "payment":
                stmt = (
                    update(PaymentModel)
                    .where(PaymentModel.payment_id == transaction_id)
                    .where(
                        PaymentModel.client_id == context.user.client_id
                        if not context.is_super_admin
                        else True
                    )
                    .values(
                        amount=data.get("amount"),
                        method=data.get("category"),
                        reference=data.get("reference"),
                        notes=data.get("note"),
                        paid_at=data.get("entry_date"),
                    )
                )
                result = session.execute(stmt)
                session.commit()
                if result.rowcount == 0:
                    raise ValueError("Payment not found or not authorized")
                payment = session.get(PaymentModel, transaction_id)
                return self._payment_to_transaction(payment)

            elif transaction_type == "expense":
                stmt = (
                    update(ExpenseModel)
                    .where(ExpenseModel.expense_id == transaction_id)
                    .where(
                        ExpenseModel.client_id == context.user.client_id
                        if not context.is_super_admin
                        else True
                    )
                    .values(
                        amount=data.get("amount"),
                        category=data.get("category"),
                        description=data.get("note"),
                        vendor_name=data.get("vendor_name"),
                        expense_number=data.get("reference"),
                        incurred_at=data.get("entry_date"),
                        payment_status=data.get("payment_status", "unpaid"),
                    )
                )
                result = session.execute(stmt)
                session.commit()
                if result.rowcount == 0:
                    raise ValueError("Expense not found or not authorized")
                expense = session.get(ExpenseModel, transaction_id)
                return self._expense_to_transaction(expense)

            else:
                raise ValueError(f"Unsupported transaction type: {transaction_type}")