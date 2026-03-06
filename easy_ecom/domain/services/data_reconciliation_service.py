from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import SalesOrderItemsRepo, SalesOrdersRepo


@dataclass(frozen=True)
class ReconciliationIssue:
    issue_type: str
    severity: str
    client_id: str
    reference_id: str
    message: str


class DataReconciliationService:
    """Shared normalization + reconciliation for dashboard and operational pages."""

    def __init__(
        self,
        inventory_repo: InventoryTxnRepo,
        products_repo: ProductsRepo,
        variants_repo: ProductVariantsRepo | None,
        orders_repo: SalesOrdersRepo | None,
        order_items_repo: SalesOrderItemsRepo | None,
        ledger_repo: LedgerRepo | None,
    ):
        self.inventory_repo = inventory_repo
        self.products_repo = products_repo
        self.variants_repo = variants_repo
        self.orders_repo = orders_repo
        self.order_items_repo = order_items_repo
        self.ledger_repo = ledger_repo

    @staticmethod
    def _to_float(series: pd.Series) -> pd.Series:
        return pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)

    @staticmethod
    def _scope(df: pd.DataFrame, client_id: str | None) -> pd.DataFrame:
        if df.empty or not client_id or "client_id" not in df.columns:
            return df.copy()
        return df[df["client_id"] == client_id].copy()

    def product_map(self, client_id: str | None) -> pd.DataFrame:
        products = self._scope(self.products_repo.all(), client_id)
        if products.empty:
            return pd.DataFrame(columns=["product_id", "product_name"])
        return products[["product_id", "product_name"]].drop_duplicates()

    def variant_map(self, client_id: str | None) -> pd.DataFrame:
        if self.variants_repo is None:
            return pd.DataFrame(
                columns=["variant_id", "variant_name", "parent_product_id", "parent_product_name"]
            )
        variants = self._scope(self.variants_repo.all(), client_id)
        if variants.empty:
            return pd.DataFrame(
                columns=["variant_id", "variant_name", "parent_product_id", "parent_product_name"]
            )
        parent = self.product_map(client_id).rename(
            columns={"product_id": "parent_product_id", "product_name": "parent_product_name"}
        )
        return variants[["variant_id", "variant_name", "parent_product_id"]].merge(
            parent, on="parent_product_id", how="left"
        )

    def normalized_inventory_rows(self, client_id: str | None) -> pd.DataFrame:
        inv = self._scope(self.inventory_repo.all(), client_id)
        if inv.empty:
            return pd.DataFrame(
                columns=[
                    "txn_id",
                    "client_id",
                    "txn_type",
                    "product_id",
                    "product_name",
                    "canonical_product_id",
                    "canonical_product_name",
                    "inventory_product_id",
                    "inventory_product_name",
                    "parent_product_id",
                    "parent_product_name",
                    "variant_id",
                    "variant_name",
                    "lot_id",
                    "qty",
                    "unit_cost",
                    "total_cost",
                    "is_unmapped",
                    "issue_reason",
                ]
            )
        d = inv.copy()
        d["product_id"] = d.get("product_id", "").astype(str)
        product_name_col = (
            d["product_name"] if "product_name" in d.columns else pd.Series("", index=d.index)
        )
        d["product_name"] = product_name_col.astype(str)
        d["qty"] = self._to_float(d["qty"] if "qty" in d.columns else pd.Series(0.0, index=d.index))
        d["unit_cost"] = self._to_float(
            d["unit_cost"] if "unit_cost" in d.columns else pd.Series(0.0, index=d.index)
        )
        d["total_cost"] = self._to_float(
            d["total_cost"] if "total_cost" in d.columns else pd.Series(0.0, index=d.index)
        )

        products = self.product_map(client_id)
        variants = self.variant_map(client_id)
        by_id = set(products["product_id"].astype(str)) if not products.empty else set()
        variant_by_id = (
            variants.set_index(variants["variant_id"].astype(str)).to_dict(orient="index")
            if not variants.empty
            else {}
        )
        by_name = (
            products.set_index(products["product_name"].astype(str).str.strip().str.lower())[
                "product_id"
            ].to_dict()
            if not products.empty
            else {}
        )

        def resolve(row: pd.Series) -> dict[str, str]:
            raw_pid = str(row.get("product_id", "")).strip()
            raw_name = str(row.get("product_name", "")).strip()
            if raw_pid in by_id:
                return {
                    "canonical_product_id": raw_pid,
                    "parent_product_id": raw_pid,
                    "variant_id": "",
                    "variant_name": "",
                    "issue_reason": "",
                }
            if raw_pid in variant_by_id:
                v = variant_by_id[raw_pid]
                parent_product_id = str(v.get("parent_product_id", "")).strip()
                return {
                    "canonical_product_id": parent_product_id,
                    "parent_product_id": parent_product_id,
                    "variant_id": raw_pid,
                    "variant_name": str(v.get("variant_name", "")).strip(),
                    "issue_reason": "",
                }
            if raw_name and raw_name.lower() in by_name:
                mapped = str(by_name[raw_name.lower()])
                return {
                    "canonical_product_id": mapped,
                    "parent_product_id": mapped,
                    "variant_id": "",
                    "variant_name": "",
                    "issue_reason": "mapped_from_product_name",
                }
            if raw_pid and "_LOT-" in raw_pid:
                prefix = raw_pid.split("_LOT-", 1)[0].strip()
                if prefix in by_id:
                    return {
                        "canonical_product_id": prefix,
                        "parent_product_id": prefix,
                        "variant_id": "",
                        "variant_name": "",
                        "issue_reason": "mapped_from_legacy_lot_product_id",
                    }
            if raw_pid:
                return {
                    "canonical_product_id": raw_pid,
                    "parent_product_id": raw_pid,
                    "variant_id": "",
                    "variant_name": "",
                    "issue_reason": "unmapped_product_id",
                }
            if raw_name:
                missing = f"UNMAPPED::{raw_name}"
                return {
                    "canonical_product_id": missing,
                    "parent_product_id": missing,
                    "variant_id": "",
                    "variant_name": "",
                    "issue_reason": "missing_product_id_mapped_to_name_key",
                }
            return {
                "canonical_product_id": "UNMAPPED::MISSING",
                "parent_product_id": "UNMAPPED::MISSING",
                "variant_id": "",
                "variant_name": "",
                "issue_reason": "missing_product_reference",
            }

        resolved = d.apply(resolve, axis=1)
        d["canonical_product_id"] = resolved.apply(lambda v: v["canonical_product_id"])
        d["parent_product_id"] = resolved.apply(lambda v: v["parent_product_id"])
        d["variant_id"] = resolved.apply(lambda v: v["variant_id"])
        d["variant_name"] = resolved.apply(lambda v: v["variant_name"])
        d["issue_reason"] = resolved.apply(lambda v: v["issue_reason"])
        d["is_unmapped"] = (~d["canonical_product_id"].isin(by_id)).astype(bool) if by_id else True

        named = products.rename(
            columns={"product_id": "canonical_product_id", "product_name": "canonical_product_name"}
        )
        d = d.merge(named, on="canonical_product_id", how="left")
        d = d.merge(
            products.rename(
                columns={"product_id": "parent_product_id", "product_name": "parent_product_name"}
            ),
            on="parent_product_id",
            how="left",
        )
        d["canonical_product_name"] = (
            d["canonical_product_name"].fillna(d["product_name"]).fillna(d["canonical_product_id"])
        )
        d["parent_product_name"] = (
            d["parent_product_name"]
            .fillna(d["canonical_product_name"])
            .fillna(d["parent_product_id"])
        )
        d["variant_name"] = d["variant_name"].where(
            d["variant_name"].astype(str).str.strip() != "", d["product_name"]
        )
        d["inventory_product_id"] = d["variant_id"].where(
            d["variant_id"].astype(str).str.strip() != "", d["canonical_product_id"]
        )
        d["inventory_product_name"] = d["variant_name"].where(
            d["variant_id"].astype(str).str.strip() != "", d["canonical_product_name"]
        )
        return d

    def inventory_stock_by_lot(self, client_id: str | None) -> pd.DataFrame:
        d = self.normalized_inventory_rows(client_id)
        if d.empty:
            return pd.DataFrame(
                columns=[
                    "product_name",
                    "product_id",
                    "parent_product_id",
                    "parent_product_name",
                    "variant_id",
                    "variant_name",
                    "lot_id",
                    "qty",
                    "unit_cost",
                    "is_unmapped",
                    "issue_reason",
                ]
            )
        inbound = {"IN", "ADJUST+", "ADJUST"}
        d["signed_qty"] = d.apply(
            lambda r: r["qty"] if r["txn_type"] in inbound else -r["qty"], axis=1
        )
        g = (
            d.groupby(
                [
                    "inventory_product_name",
                    "inventory_product_id",
                    "parent_product_id",
                    "parent_product_name",
                    "variant_id",
                    "variant_name",
                    "lot_id",
                    "is_unmapped",
                    "issue_reason",
                ],
                as_index=False,
            )
            .agg(qty=("signed_qty", "sum"), unit_cost=("unit_cost", "last"))
            .rename(
                columns={
                    "inventory_product_name": "product_name",
                    "inventory_product_id": "product_id",
                }
            )
        )
        return g[g["qty"] > 0].copy()

    def confirmed_sales_with_reconciliation(
        self, client_id: str | None, latest_limit: int | None = 50
    ) -> pd.DataFrame:
        if self.orders_repo is None:
            return pd.DataFrame(
                columns=[
                    "order_id",
                    "client_id",
                    "timestamp",
                    "status",
                    "grand_total",
                    "has_items",
                    "items_total",
                    "ledger_earning_amount",
                    "has_ledger_earning",
                    "ledger_mismatch",
                ]
            )
        orders = self._scope(self.orders_repo.all(), client_id)
        if orders.empty:
            return pd.DataFrame(
                columns=[
                    "order_id",
                    "client_id",
                    "timestamp",
                    "status",
                    "grand_total",
                    "has_items",
                    "items_total",
                    "ledger_earning_amount",
                    "has_ledger_earning",
                    "ledger_mismatch",
                ]
            )
        confirmed = orders[orders["status"].fillna("") == "confirmed"].copy()
        if confirmed.empty:
            return confirmed
        confirmed["timestamp"] = pd.to_datetime(confirmed["timestamp"], errors="coerce")
        confirmed["grand_total"] = self._to_float(
            confirmed.get("grand_total", pd.Series(dtype=float))
        )

        items = self.order_items_repo.all() if self.order_items_repo is not None else pd.DataFrame()
        if not items.empty:
            items["qty"] = self._to_float(items.get("qty", pd.Series(dtype=float)))
            items["total_selling_price"] = self._to_float(
                items.get("total_selling_price", pd.Series(dtype=float))
            )
            summary = items.groupby("order_id", as_index=False).agg(
                item_count=("order_item_id", "count"), items_total=("total_selling_price", "sum")
            )
        else:
            summary = pd.DataFrame(columns=["order_id", "item_count", "items_total"])

        ledger = (
            self._scope(self.ledger_repo.all(), client_id)
            if self.ledger_repo is not None
            else pd.DataFrame()
        )
        if not ledger.empty:
            earn = ledger[
                (ledger["entry_type"] == "earning") & (ledger["source_type"] == "sale")
            ].copy()
            earn["amount"] = self._to_float(earn.get("amount", pd.Series(dtype=float)))
            ledger_sum = (
                earn.groupby("source_id", as_index=False)
                .agg(ledger_earning_amount=("amount", "sum"))
                .rename(columns={"source_id": "order_id"})
            )
        else:
            ledger_sum = pd.DataFrame(columns=["order_id", "ledger_earning_amount"])

        d = confirmed.merge(summary, on="order_id", how="left").merge(
            ledger_sum, on="order_id", how="left"
        )
        d["item_count"] = d["item_count"].fillna(0).astype(int)
        d["items_total"] = d["items_total"].fillna(0.0)
        d["has_items"] = d["item_count"] > 0
        d["ledger_earning_amount"] = d["ledger_earning_amount"].fillna(0.0)
        d["has_ledger_earning"] = d["ledger_earning_amount"] > 0
        d["ledger_mismatch"] = (d["ledger_earning_amount"] - d["grand_total"]).abs() > 0.009
        d = d.sort_values("timestamp", ascending=False)
        return d.head(latest_limit) if latest_limit else d

    def orphan_ledger_earnings(self, client_id: str | None) -> pd.DataFrame:
        if self.ledger_repo is None or self.orders_repo is None:
            return pd.DataFrame(
                columns=[
                    "entry_id",
                    "client_id",
                    "source_id",
                    "amount",
                    "timestamp",
                    "issue_reason",
                ]
            )
        ledger = self._scope(self.ledger_repo.all(), client_id)
        if ledger.empty:
            return pd.DataFrame(
                columns=[
                    "entry_id",
                    "client_id",
                    "source_id",
                    "amount",
                    "timestamp",
                    "issue_reason",
                ]
            )
        earning = ledger[
            (ledger["entry_type"] == "earning") & (ledger["source_type"] == "sale")
        ].copy()
        if earning.empty:
            return pd.DataFrame(
                columns=[
                    "entry_id",
                    "client_id",
                    "source_id",
                    "amount",
                    "timestamp",
                    "issue_reason",
                ]
            )
        orders = self._scope(self.orders_repo.all(), client_id)
        order_ids = set(orders["order_id"].astype(str)) if not orders.empty else set()
        missing = earning[~earning["source_id"].astype(str).isin(order_ids)].copy()
        if missing.empty:
            return pd.DataFrame(
                columns=[
                    "entry_id",
                    "client_id",
                    "source_id",
                    "amount",
                    "timestamp",
                    "issue_reason",
                ]
            )
        missing["issue_reason"] = "ledger_earning_without_sales_order"
        return missing[
            ["entry_id", "client_id", "source_id", "amount", "timestamp", "issue_reason"]
        ]

    def integrity_issues(self, client_id: str | None) -> list[ReconciliationIssue]:
        issues: list[ReconciliationIssue] = []
        inv = self.normalized_inventory_rows(client_id)
        if not inv.empty:
            unmapped = inv[inv["is_unmapped"]]
            for _, row in unmapped.iterrows():
                issues.append(
                    ReconciliationIssue(
                        issue_type="inventory_unmapped_product",
                        severity="warning",
                        client_id=str(row.get("client_id", client_id or "")),
                        reference_id=str(row.get("txn_id", "")),
                        message=f"Inventory row has unmapped product reference ({row.get('issue_reason', 'unknown')}).",
                    )
                )
            out_missing_lot = inv[
                (inv["txn_type"] == "OUT") & (inv["lot_id"].astype(str).str.strip() == "")
            ]
            for _, row in out_missing_lot.iterrows():
                issues.append(
                    ReconciliationIssue(
                        issue_type="inventory_out_missing_lot",
                        severity="error",
                        client_id=str(row.get("client_id", client_id or "")),
                        reference_id=str(row.get("txn_id", "")),
                        message="OUT inventory row is missing lot_id.",
                    )
                )

        sales = self.confirmed_sales_with_reconciliation(client_id, latest_limit=None)
        if not sales.empty:
            no_items = sales[~sales["has_items"]]
            for _, row in no_items.iterrows():
                issues.append(
                    ReconciliationIssue(
                        issue_type="sales_order_without_items",
                        severity="error",
                        client_id=str(row.get("client_id", client_id or "")),
                        reference_id=str(row.get("order_id", "")),
                        message="Confirmed sales order has no items.",
                    )
                )

        orphan_ledger = self.orphan_ledger_earnings(client_id)
        for _, row in orphan_ledger.iterrows():
            issues.append(
                ReconciliationIssue(
                    issue_type="orphan_ledger_earning",
                    severity="warning",
                    client_id=str(row.get("client_id", client_id or "")),
                    reference_id=str(row.get("entry_id", "")),
                    message="Ledger earning exists without matching sales order.",
                )
            )

        if client_id and self.orders_repo is not None and self.order_items_repo is not None:
            orders = self.orders_repo.all()
            order_ids = (
                self._scope(orders, client_id)[["order_id"]]
                if not orders.empty
                else pd.DataFrame(columns=["order_id"])
            )
            items = self.order_items_repo.all()
            if not items.empty and not order_ids.empty:
                linked_items = items.merge(order_ids, on="order_id", how="inner")
                inv_all = self.inventory_repo.all()
                if not inv_all.empty:
                    linked_out = self._scope(inv_all, client_id)
                    linked_out = linked_out[
                        (linked_out["source_type"] == "sale") & (linked_out["txn_type"] == "OUT")
                    ]
                    mismatch = linked_out[
                        ~linked_out["source_id"]
                        .astype(str)
                        .isin(set(order_ids["order_id"].astype(str)))
                    ]
                    for _, row in mismatch.iterrows():
                        issues.append(
                            ReconciliationIssue(
                                issue_type="client_id_mismatch_linked_records",
                                severity="error",
                                client_id=str(row.get("client_id", "")),
                                reference_id=str(row.get("txn_id", "")),
                                message="Inventory sale transaction source_id does not match any scoped sales order.",
                            )
                        )
        return issues
