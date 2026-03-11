from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from easy_ecom.data.repos.base import TabularRepo


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
        inventory_repo: TabularRepo,
        products_repo: TabularRepo,
        variants_repo: TabularRepo | None,
        orders_repo: TabularRepo | None,
        order_items_repo: TabularRepo | None,
        ledger_repo: TabularRepo | None,
        invoices_repo: TabularRepo | None = None,
    ):
        self.inventory_repo = inventory_repo
        self.products_repo = products_repo
        self.variants_repo = variants_repo
        self.orders_repo = orders_repo
        self.order_items_repo = order_items_repo
        self.ledger_repo = ledger_repo
        self.invoices_repo = invoices_repo

    def _sale_source_to_order_id(self, client_id: str | None) -> dict[str, str]:
        if self.invoices_repo is None:
            return {}
        invoices = self._scope(self.invoices_repo.all(), client_id)
        if invoices.empty:
            return {}
        invoice_ids = invoices.get("invoice_id", pd.Series(dtype=str)).astype(str).str.strip()
        order_ids = invoices.get("order_id", pd.Series(dtype=str)).astype(str).str.strip()
        return {
            invoice_id: order_id
            for invoice_id, order_id in zip(invoice_ids, order_ids)
            if invoice_id and order_id
        }

    def _normalize_sale_source_order_ids(
        self, source_ids: pd.Series, client_id: str | None
    ) -> pd.Series:
        normalized = source_ids.astype(str).str.strip()
        mapping = self._sale_source_to_order_id(client_id)
        if mapping:
            normalized = normalized.replace(mapping)
        return normalized

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
        outbound = {"OUT"}
        d["signed_qty"] = d.apply(
            lambda r: r["qty"] if r["txn_type"] in inbound else (-r["qty"] if r["txn_type"] in outbound else 0.0),
            axis=1,
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
            earn["order_id"] = self._normalize_sale_source_order_ids(
                earn.get("source_id", pd.Series("", index=earn.index)), client_id
            )
            earn["amount"] = self._to_float(earn.get("amount", pd.Series(dtype=float)))
            ledger_sum = earn.groupby("order_id", as_index=False).agg(
                ledger_earning_amount=("amount", "sum")
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

    def normalized_sales_items(self, client_id: str | None) -> pd.DataFrame:
        columns = [
            "order_item_id",
            "order_id",
            "client_id",
            "order_status",
            "order_timestamp",
            "inventory_product_id",
            "parent_product_id",
            "variant_id",
            "canonical_product_id",
            "product_name_snapshot",
            "variant_name_snapshot",
            "raw_product_id",
            "identity_status",
            "identity_issue_reason",
            "qty",
            "unit_selling_price",
            "line_total",
            "has_ledger_earning",
            "ledger_earning_amount",
            "ledger_mismatch",
        ]
        if self.order_items_repo is None:
            return pd.DataFrame(columns=columns)

        items = self.order_items_repo.all()
        if items.empty:
            return pd.DataFrame(columns=columns)

        orders = (
            self._scope(self.orders_repo.all(), client_id)
            if self.orders_repo is not None
            else pd.DataFrame(
                columns=["order_id", "client_id", "status", "timestamp", "grand_total"]
            )
        )
        if orders.empty:
            return pd.DataFrame(columns=columns)

        order_view = orders[["order_id", "client_id", "status", "timestamp", "grand_total"]].rename(
            columns={"status": "order_status", "timestamp": "order_timestamp"}
        )
        d = items.merge(order_view, on="order_id", how="inner")
        if d.empty:
            return pd.DataFrame(columns=columns)

        if "client_id" not in d.columns:
            d["client_id"] = ""
        if "client_id_x" in d.columns:
            d["client_id"] = d["client_id"].where(
                d["client_id"].astype(str).str.strip() != "", d["client_id_x"]
            )
        if "client_id_y" in d.columns:
            d["client_id"] = d["client_id"].where(
                d["client_id"].astype(str).str.strip() != "", d["client_id_y"]
            )

        d["raw_product_id"] = d.get("product_id", "").astype(str).str.strip()
        d["prd_description_snapshot"] = d.get(
            "prd_description_snapshot", pd.Series("", index=d.index)
        ).astype(str)
        d["qty"] = self._to_float(d.get("qty", pd.Series(0.0, index=d.index)))
        d["unit_selling_price"] = self._to_float(
            d.get("unit_selling_price", pd.Series(0.0, index=d.index))
        )
        d["line_total"] = self._to_float(
            d.get("total_selling_price", pd.Series(0.0, index=d.index))
        )

        products = self.product_map(client_id)
        product_ids = set(products["product_id"].astype(str)) if not products.empty else set()
        product_names = (
            products.set_index(products["product_name"].astype(str).str.strip().str.lower())[
                "product_id"
            ].to_dict()
            if not products.empty
            else {}
        )
        product_name_by_id = (
            products.set_index(products["product_id"].astype(str))["product_name"].to_dict()
            if not products.empty
            else {}
        )

        variants = self.variant_map(client_id)
        variant_by_id = (
            variants.set_index(variants["variant_id"].astype(str)).to_dict(orient="index")
            if not variants.empty
            else {}
        )

        def resolve(row: pd.Series) -> dict[str, str]:
            raw_pid = str(row.get("raw_product_id", "")).strip()
            desc = str(row.get("prd_description_snapshot", "")).strip()
            if raw_pid in product_ids:
                pname = str(product_name_by_id.get(raw_pid, "")).strip() or desc or raw_pid
                return {
                    "inventory_product_id": raw_pid,
                    "parent_product_id": raw_pid,
                    "variant_id": "",
                    "canonical_product_id": raw_pid,
                    "product_name_snapshot": pname,
                    "variant_name_snapshot": "",
                    "identity_status": "valid_parent_item",
                    "identity_issue_reason": "",
                }
            if raw_pid in variant_by_id:
                vm = variant_by_id[raw_pid]
                parent = str(vm.get("parent_product_id", "")).strip()
                parent_name = str(vm.get("parent_product_name", "")).strip() or desc or parent
                variant_name = str(vm.get("variant_name", "")).strip()
                return {
                    "inventory_product_id": raw_pid,
                    "parent_product_id": parent,
                    "variant_id": raw_pid,
                    "canonical_product_id": parent,
                    "product_name_snapshot": parent_name,
                    "variant_name_snapshot": variant_name,
                    "identity_status": "valid_variant_item",
                    "identity_issue_reason": "",
                }
            if raw_pid and raw_pid.lower() in product_names:
                mapped_parent = str(product_names[raw_pid.lower()]).strip()
                pname = str(product_name_by_id.get(mapped_parent, "")).strip() or raw_pid
                return {
                    "inventory_product_id": mapped_parent,
                    "parent_product_id": mapped_parent,
                    "variant_id": "",
                    "canonical_product_id": mapped_parent,
                    "product_name_snapshot": pname,
                    "variant_name_snapshot": "",
                    "identity_status": "legacy_repairable_row",
                    "identity_issue_reason": "mapped_from_legacy_product_name_in_product_id",
                }
            if desc and desc.lower() in product_names:
                mapped_parent = str(product_names[desc.lower()]).strip()
                pname = str(product_name_by_id.get(mapped_parent, "")).strip() or desc
                return {
                    "inventory_product_id": mapped_parent,
                    "parent_product_id": mapped_parent,
                    "variant_id": "",
                    "canonical_product_id": mapped_parent,
                    "product_name_snapshot": pname,
                    "variant_name_snapshot": "",
                    "identity_status": "legacy_repairable_row",
                    "identity_issue_reason": "mapped_from_legacy_description_snapshot",
                }
            unresolved = raw_pid or desc or "UNMAPPED::MISSING"
            return {
                "inventory_product_id": unresolved,
                "parent_product_id": unresolved,
                "variant_id": "",
                "canonical_product_id": unresolved,
                "product_name_snapshot": desc or unresolved,
                "variant_name_snapshot": "",
                "identity_status": "unknown_or_broken_row",
                "identity_issue_reason": "unknown_product_reference",
            }

        resolved = d.apply(resolve, axis=1)
        for col in [
            "inventory_product_id",
            "parent_product_id",
            "variant_id",
            "canonical_product_id",
            "product_name_snapshot",
            "variant_name_snapshot",
            "identity_status",
            "identity_issue_reason",
        ]:
            d[col] = resolved.apply(lambda v: v[col])

        confirmed_sales = self.confirmed_sales_with_reconciliation(client_id, latest_limit=None)
        if confirmed_sales.empty:
            d["has_ledger_earning"] = False
            d["ledger_earning_amount"] = 0.0
            d["ledger_mismatch"] = False
        else:
            ledger_cols = confirmed_sales[
                ["order_id", "has_ledger_earning", "ledger_earning_amount", "ledger_mismatch"]
            ]
            d = d.merge(ledger_cols, on="order_id", how="left")
            d["has_ledger_earning"] = d["has_ledger_earning"].fillna(False).astype(bool)
            d["ledger_earning_amount"] = d["ledger_earning_amount"].fillna(0.0)
            d["ledger_mismatch"] = d["ledger_mismatch"].fillna(False).astype(bool)

        return d[columns].copy()

    def reconciliation_health_summary(self, client_id: str | None) -> dict[str, int]:
        sales = self.confirmed_sales_with_reconciliation(client_id, latest_limit=None)
        sales_items = self.normalized_sales_items(client_id)
        inv = self.normalized_inventory_rows(client_id)
        issues = self.integrity_issues(client_id)

        return {
            "confirmed_sales_with_items": int(
                len(sales[(sales["has_items"])]) if not sales.empty else 0
            ),
            "confirmed_sales_missing_items": int(
                len(sales[~sales["has_items"]]) if not sales.empty else 0
            ),
            "confirmed_sales_with_ledger_post": int(
                len(sales[sales["has_ledger_earning"]]) if not sales.empty else 0
            ),
            "orphan_ledger_sale_earnings": int(
                len([i for i in issues if i.issue_type == "orphan_ledger_earning"])
            ),
            "valid_variant_linked_sales_items": int(
                len(sales_items[sales_items["identity_status"] == "valid_variant_item"])
                if not sales_items.empty
                else 0
            ),
            "legacy_repairable_sales_item_rows": int(
                len(sales_items[sales_items["identity_status"] == "legacy_repairable_row"])
                if not sales_items.empty
                else 0
            ),
            "truly_broken_sales_item_identities": int(
                len(sales_items[sales_items["identity_status"] == "unknown_or_broken_row"])
                if not sales_items.empty
                else 0
            ),
            "unmapped_inventory_rows": int(len(inv[inv["is_unmapped"]]) if not inv.empty else 0),
            "client_mismatch_issues": int(
                len([i for i in issues if i.issue_type == "client_id_mismatch_linked_records"])
            ),
        }

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
        normalized_sources = self._normalize_sale_source_order_ids(
            earning.get("source_id", pd.Series("", index=earning.index)), client_id
        )
        missing = earning[~normalized_sources.isin(order_ids)].copy()
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
        sales_items = self.normalized_sales_items(client_id)
        if not sales_items.empty:
            broken_rows = sales_items[sales_items["identity_status"] == "unknown_or_broken_row"]
            for _, row in broken_rows.iterrows():
                issues.append(
                    ReconciliationIssue(
                        issue_type="sales_item_invalid_identity",
                        severity="error",
                        client_id=str(row.get("client_id", client_id or "")),
                        reference_id=str(row.get("order_item_id", "")),
                        message="Sales order item has unknown/broken product identity.",
                    )
                )
        return issues
