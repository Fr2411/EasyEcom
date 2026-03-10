from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.store.postgres_models import CustomerModel, FinanceExpenseModel, SalesOrderModel


@dataclass
class ExpenseCreateInput:
    expense_date: str
    category: str
    amount: float
    note: str
    payment_status: str


@dataclass
class ExpenseUpdateInput:
    expense_date: str
    category: str
    amount: float
    note: str
    payment_status: str


class FinanceApiService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    @staticmethod
    def _to_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_payment_status(value: str) -> str:
        status = value.strip().lower()
        if status not in {"paid", "unpaid", "partial"}:
            raise ValueError("payment_status must be one of: paid, unpaid, partial")
        return status

    @staticmethod
    def _validate_iso_date(value: str) -> str:
        raw = value.strip()
        try:
            date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("expense_date must be ISO format YYYY-MM-DD") from exc
        return raw

    def create_expense(self, *, client_id: str, user_id: str, payload: ExpenseCreateInput) -> dict[str, object]:
        expense_id = new_uuid()
        expense_date = self._validate_iso_date(payload.expense_date)
        category = payload.category.strip()
        if not category:
            raise ValueError("category is required")
        status = self._normalize_payment_status(payload.payment_status)

        with self.session_factory() as session:
            row = FinanceExpenseModel(
                expense_id=expense_id,
                client_id=client_id,
                expense_date=expense_date,
                category=category,
                amount=str(float(payload.amount)),
                payment_status=status,
                note=payload.note.strip(),
                created_by_user_id=user_id,
                created_at=now_iso(),
                updated_at=now_iso(),
            )
            session.add(row)
            session.commit()

        return self.get_expense(client_id=client_id, expense_id=expense_id)

    def update_expense(self, *, client_id: str, expense_id: str, payload: ExpenseUpdateInput) -> dict[str, object] | None:
        with self.session_factory() as session:
            row = session.execute(
                select(FinanceExpenseModel).where(
                    FinanceExpenseModel.client_id == client_id,
                    FinanceExpenseModel.expense_id == expense_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return None

            row.expense_date = self._validate_iso_date(payload.expense_date)
            row.category = payload.category.strip()
            if not row.category:
                raise ValueError("category is required")
            row.amount = str(float(payload.amount))
            row.note = payload.note.strip()
            row.payment_status = self._normalize_payment_status(payload.payment_status)
            row.updated_at = now_iso()
            session.commit()

        return self.get_expense(client_id=client_id, expense_id=expense_id)

    def get_expense(self, *, client_id: str, expense_id: str) -> dict[str, object] | None:
        with self.session_factory() as session:
            row = session.execute(
                select(FinanceExpenseModel).where(
                    FinanceExpenseModel.client_id == client_id,
                    FinanceExpenseModel.expense_id == expense_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return {
                "expense_id": row.expense_id,
                "expense_date": row.expense_date,
                "category": row.category,
                "amount": self._to_float(row.amount),
                "payment_status": row.payment_status,
                "note": row.note,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }

    def list_expenses(self, *, client_id: str, query: str = "", payment_status: str = "") -> list[dict[str, object]]:
        with self.session_factory() as session:
            stmt = select(FinanceExpenseModel).where(FinanceExpenseModel.client_id == client_id)
            if query.strip():
                needle = f"%{query.strip()}%"
                stmt = stmt.where(
                    or_(
                        FinanceExpenseModel.category.ilike(needle),
                        FinanceExpenseModel.note.ilike(needle),
                        FinanceExpenseModel.expense_date.ilike(needle),
                    )
                )
            if payment_status.strip():
                stmt = stmt.where(FinanceExpenseModel.payment_status == self._normalize_payment_status(payment_status))
            rows = session.execute(stmt.order_by(FinanceExpenseModel.expense_date.desc(), FinanceExpenseModel.created_at.desc()).limit(500)).scalars().all()

        return [
            {
                "expense_id": row.expense_id,
                "expense_date": row.expense_date,
                "category": row.category,
                "amount": self._to_float(row.amount),
                "payment_status": row.payment_status,
                "note": row.note,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]

    def finance_overview(self, *, client_id: str) -> dict[str, float | None]:
        with self.session_factory() as session:
            revenue = session.execute(
                select(func.sum(SalesOrderModel.grand_total)).where(SalesOrderModel.client_id == client_id)
            ).scalar_one_or_none()
            expenses = session.execute(
                select(func.sum(FinanceExpenseModel.amount)).where(FinanceExpenseModel.client_id == client_id)
            ).scalar_one_or_none()
            receivables = session.execute(
                select(func.sum(SalesOrderModel.outstanding_balance)).where(
                    SalesOrderModel.client_id == client_id,
                    SalesOrderModel.payment_status.in_(["unpaid", "partial"]),
                )
            ).scalar_one_or_none()
            payables = session.execute(
                select(func.sum(FinanceExpenseModel.amount)).where(
                    FinanceExpenseModel.client_id == client_id,
                    FinanceExpenseModel.payment_status.in_(["unpaid", "partial"]),
                )
            ).scalar_one_or_none()

        revenue_value = self._to_float(revenue)
        expense_value = self._to_float(expenses)
        receivable_value = self._to_float(receivables)
        payable_value = self._to_float(payables)
        return {
            "sales_revenue": revenue_value,
            "expense_total": expense_value,
            "receivables": receivable_value,
            "payables": payable_value,
            "cash_in": revenue_value,
            "cash_out": expense_value,
            "net_operating": revenue_value - expense_value,
        }

    def list_receivables(self, *, client_id: str) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = session.execute(
                select(SalesOrderModel, CustomerModel)
                .outerjoin(
                    CustomerModel,
                    and_(
                        CustomerModel.customer_id == SalesOrderModel.customer_id,
                        CustomerModel.client_id == SalesOrderModel.client_id,
                    ),
                )
                .where(
                    SalesOrderModel.client_id == client_id,
                    SalesOrderModel.payment_status.in_(["unpaid", "partial"]),
                )
                .order_by(SalesOrderModel.timestamp.desc())
                .limit(500)
            ).all()

        return [
            {
                "sale_id": sale.order_id,
                "sale_no": sale.sale_no,
                "customer_id": sale.customer_id,
                "customer_name": customer.full_name if customer else "",
                "sale_date": sale.timestamp,
                "grand_total": self._to_float(sale.grand_total),
                "amount_paid": self._to_float(sale.amount_paid),
                "outstanding_balance": self._to_float(sale.outstanding_balance),
                "payment_status": sale.payment_status,
            }
            for sale, customer in rows
        ]

    def list_payables(self, *, client_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            payable_count = session.execute(
                select(func.count(FinanceExpenseModel.expense_id)).where(
                    FinanceExpenseModel.client_id == client_id,
                    FinanceExpenseModel.payment_status.in_(["unpaid", "partial"]),
                )
            ).scalar_one()
        return {
            "supported": True,
            "deferred_reason": "",
            "rows": self.list_expenses(client_id=client_id, payment_status="unpaid") + self.list_expenses(client_id=client_id, payment_status="partial"),
            "unpaid_count": int(payable_count or 0),
        }

    def list_transactions(self, *, client_id: str) -> list[dict[str, object]]:
        with self.session_factory() as session:
            expenses = session.execute(
                select(FinanceExpenseModel).where(FinanceExpenseModel.client_id == client_id)
            ).scalars().all()
            sales = session.execute(
                select(SalesOrderModel).where(SalesOrderModel.client_id == client_id)
            ).scalars().all()

        rows: list[dict[str, object]] = []
        for expense in expenses:
            rows.append(
                {
                    "entry_id": expense.expense_id,
                    "entry_date": expense.expense_date,
                    "entry_type": "expense",
                    "category": expense.category,
                    "amount": self._to_float(expense.amount),
                    "direction": "out",
                    "reference": expense.expense_id,
                    "note": expense.note,
                }
            )
        for sale in sales:
            rows.append(
                {
                    "entry_id": sale.order_id,
                    "entry_date": sale.timestamp,
                    "entry_type": "sale",
                    "category": "Sales",
                    "amount": self._to_float(sale.grand_total),
                    "direction": "in",
                    "reference": sale.sale_no,
                    "note": sale.note,
                }
            )
        rows.sort(key=lambda row: (str(row["entry_date"]), str(row["entry_id"])), reverse=True)
        return rows[:1000]
