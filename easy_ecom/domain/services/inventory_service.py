from __future__ import annotations

import pandas as pd

from easy_ecom.core.config import settings
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo


class SequenceService:
    def __init__(self, repo: SequencesRepo):
        self.repo = repo

    def next(self, client_id: str, sequence_key: str, year: int, prefix: str) -> str:
        df = self.repo.all()
        mask = (df["client_id"] == client_id) & (df["sequence_key"] == sequence_key) & (df["year"] == str(year))
        if df.empty or df[mask].empty:
            last_number = 1
            self.repo.append({"client_id": client_id, "sequence_key": sequence_key, "year": str(year), "last_number": str(last_number)})
        else:
            idx = df[mask].index[0]
            last_number = int(df.loc[idx, "last_number"]) + 1
            df.loc[idx, "last_number"] = str(last_number)
            self.repo.save(df)
        return f"{prefix}-{year}-{last_number:05d}"


class InventoryService:
    def __init__(self, repo: InventoryTxnRepo, seq_service: SequenceService):
        self.repo = repo
        self.seq_service = seq_service

    @staticmethod
    def _product_name_from_txn_row(row: pd.Series) -> str:
        if "product_name" in row and str(row["product_name"]).strip():
            return str(row["product_name"])
        return str(row.get("product_id", ""))

    def add_stock(self, client_id: str, product_id: str, product_name: str, qty: float, unit_cost: float, supplier_snapshot: str, note: str, source_type: str = "purchase", source_id: str = "", user_id: str = "") -> str:
        if qty <= 0 or unit_cost <= 0:
            raise ValueError("qty and unit_cost must be > 0")
        lot_id = self.seq_service.next(client_id, "LOT", pd.Timestamp.utcnow().year, "LOT")
        self.repo.append({"txn_id": new_uuid(), "client_id": client_id, "timestamp": now_iso(), "user_id": user_id, "txn_type": "IN", "product_id": product_id, "product_name": product_name, "qty": str(qty), "unit_cost": str(unit_cost), "total_cost": str(qty * unit_cost), "supplier_snapshot": supplier_snapshot, "note": note, "source_type": source_type, "source_id": source_id, "lot_id": lot_id})
        return lot_id

    def stock_by_lot(self, client_id: str) -> pd.DataFrame:
        df = self.repo.all()
        if df.empty:
            return pd.DataFrame(columns=["product_name", "product_id", "lot_id", "qty", "unit_cost"])
        d = df[df["client_id"] == client_id].copy()
        d["product_name"] = d.apply(self._product_name_from_txn_row, axis=1)
        d["qty"] = d["qty"].astype(float)
        d["signed_qty"] = d.apply(lambda r: r["qty"] if r["txn_type"] == "IN" else -r["qty"], axis=1)
        g = d.groupby(["product_name", "product_id", "lot_id"], as_index=False).agg({"signed_qty": "sum", "unit_cost": "last"})
        g = g.rename(columns={"signed_qty": "qty"})
        return g[g["qty"] > 0]

    def available_qty(self, client_id: str, product_id: str) -> float:
        lots = self.stock_by_lot(client_id)
        if lots.empty:
            return 0.0
        return float(lots[lots["product_id"] == product_id]["qty"].sum())

    def allocate_fifo(self, client_id: str, product_id: str, qty: float) -> list[dict[str, float | str]]:
        if qty <= 0:
            raise ValueError("qty must be positive")
        lots = self.stock_by_lot(client_id)
        product_lots = lots[lots["product_id"] == product_id].sort_values("lot_id")
        remaining = qty
        allocations: list[dict[str, float | str]] = []
        for _, row in product_lots.iterrows():
            if remaining <= 0:
                break
            take = min(float(row["qty"]), remaining)
            if take > 0:
                allocations.append({"lot_id": row["lot_id"], "product_id": row["product_id"], "product_name": row["product_name"], "qty": take, "unit_cost": float(row["unit_cost"])})
                remaining -= take
        if remaining > 0 and not settings.allow_backorder:
            raise ValueError("Insufficient stock")
        return allocations

    def deduct_stock(self, client_id: str, product_id: str, qty: float, source_type: str, source_id: str, note: str = "", user_id: str = "") -> list[dict[str, float | str]]:
        allocations = self.allocate_fifo(client_id, product_id, qty)
        for alloc in allocations:
            q = float(alloc["qty"])
            uc = float(alloc["unit_cost"])
            self.repo.append({"txn_id": new_uuid(), "client_id": client_id, "timestamp": now_iso(), "user_id": user_id, "txn_type": "OUT", "product_id": str(alloc["product_id"]), "product_name": str(alloc["product_name"]), "qty": str(q), "unit_cost": str(uc), "total_cost": str(q * uc), "supplier_snapshot": "", "note": note, "source_type": source_type, "source_id": source_id, "lot_id": str(alloc["lot_id"])})
        return allocations
