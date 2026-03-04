from __future__ import annotations

import pandas as pd

from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, SalesOrdersRepo


class DashboardService:
    def __init__(self, inv: InventoryTxnRepo, ledger: LedgerRepo, orders: SalesOrdersRepo, invoices: InvoicesRepo):
        self.inv = inv
        self.ledger = ledger
        self.orders = orders
        self.invoices = invoices

    def kpis(self, client_id: str) -> dict[str, float]:
        month = pd.Timestamp.utcnow().strftime("%Y-%m")
        inv = self.inv.all()
        ledger = self.ledger.all()
        orders = self.orders.all()
        invoices = self.invoices.all()
        stock_value = 0.0
        if not inv.empty:
            d = inv[inv["client_id"] == client_id].copy()
            d["qty"] = d["qty"].astype(float)
            d["signed_qty"] = d.apply(lambda r: r["qty"] if r["txn_type"] == "IN" else -r["qty"], axis=1)
            lot = d.groupby(["product_id", "lot_id"], as_index=False).agg({"signed_qty": "sum", "unit_cost": "last"})
            lot = lot[lot["signed_qty"] > 0]
            stock_value = float((lot["signed_qty"].astype(float) * lot["unit_cost"].astype(float)).sum())

        revenue = expenses = 0.0
        if not ledger.empty:
            ledger_mtd = ledger[(ledger["client_id"] == client_id) & (ledger["timestamp"].str.startswith(month))].copy()
            ledger_mtd["amount"] = ledger_mtd["amount"].astype(float)
            revenue = float(ledger_mtd[ledger_mtd["entry_type"] == "earning"]["amount"].sum())
            expenses = float(ledger_mtd[ledger_mtd["entry_type"] == "expense"]["amount"].sum())

        orders_mtd = 0
        aov = 0.0
        if not orders.empty:
            o = orders[(orders["client_id"] == client_id) & (orders["timestamp"].str.startswith(month))]
            orders_mtd = len(o)
            if orders_mtd:
                aov = float(o["grand_total"].astype(float).mean())
        outstanding = 0.0
        if not invoices.empty:
            i = invoices[(invoices["client_id"] == client_id) & (invoices["status"] != "paid")]
            outstanding = float(i["amount_due"].astype(float).sum()) if not i.empty else 0.0

        return {"stock_value": stock_value, "revenue_mtd": revenue, "expenses_mtd": expenses, "profit_mtd": revenue - expenses, "orders_mtd": float(orders_mtd), "aov_mtd": aov, "outstanding": outstanding}
