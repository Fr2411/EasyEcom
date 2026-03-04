from __future__ import annotations

import pandas as pd

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo


class FinanceService:
    def __init__(self, ledger_repo: LedgerRepo, inventory_repo: InventoryTxnRepo):
        self.ledger_repo = ledger_repo
        self.inventory_repo = inventory_repo

    def add_entry(self, client_id: str, entry_type: str, category: str, amount: float, source_type: str, source_id: str, note: str = "") -> str:
        if amount <= 0:
            raise ValueError("amount must be positive")
        entry_id = new_uuid()
        self.ledger_repo.append({"entry_id": entry_id, "client_id": client_id, "timestamp": now_iso(), "entry_type": entry_type, "category": category, "amount": str(amount), "source_type": source_type, "source_id": source_id, "note": note})
        return entry_id

    def profit_mtd(self, client_id: str) -> float:
        month = pd.Timestamp.utcnow().strftime("%Y-%m")
        ledger = self.ledger_repo.all()
        inv = self.inventory_repo.all()
        if not ledger.empty:
            ledger_mtd = ledger[(ledger["client_id"] == client_id) & (ledger["timestamp"].str.startswith(month))].copy()
            ledger_mtd["amount"] = ledger_mtd["amount"].astype(float)
            revenue = ledger_mtd[ledger_mtd["entry_type"] == "earning"]["amount"].sum()
            expenses = ledger_mtd[ledger_mtd["entry_type"] == "expense"]["amount"].sum()
        else:
            revenue = expenses = 0.0
        if not inv.empty:
            o = inv[(inv["client_id"] == client_id) & (inv["txn_type"] == "OUT") & (inv["timestamp"].str.startswith(month))].copy()
            o["total_cost"] = o["total_cost"].astype(float)
            cogs = o["total_cost"].sum()
        else:
            cogs = 0.0
        return float(revenue - expenses - cogs)
