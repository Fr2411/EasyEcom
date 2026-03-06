from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import uuid

from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import (
    InvoicesRepo,
    PaymentsRepo,
    SalesOrderItemsRepo,
    SalesOrdersRepo,
)
from easy_ecom.domain.services.data_reconciliation_service import DataReconciliationService

Granularity = Literal["D", "W", "M"]


@dataclass(frozen=True)
class DateRange:
    start: pd.Timestamp
    end: pd.Timestamp


class MetricsService:
    """Single source of truth for dashboard and finance metrics.

    Accounting source of truth for revenue/expense is `ledger.csv`.
    COGS source of truth is `inventory_txn.csv` OUT rows (`total_cost`).
    """

    def __init__(
        self,
        inv: InventoryTxnRepo,
        ledger: LedgerRepo,
        orders: SalesOrdersRepo,
        invoices: InvoicesRepo,
        payments: PaymentsRepo,
        order_items: SalesOrderItemsRepo,
        products: ProductsRepo,
        variants: ProductVariantsRepo,
    ):
        self.inv = inv
        self.ledger = ledger
        self.orders = orders
        self.invoices = invoices
        self.payments = payments
        self.order_items = order_items
        self.products = products
        self.variants = variants
        self.reconciliation = DataReconciliationService(
            inv, products, variants, orders, order_items, ledger, invoices
        )

    @staticmethod
    def to_float(series: pd.Series) -> pd.Series:
        return pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)

    @staticmethod
    def parse_timestamp(df: pd.DataFrame, col: str = "timestamp") -> pd.DataFrame:
        if df.empty or col not in df.columns:
            return df.copy()
        d = df.copy()
        d[col] = (
            pd.to_datetime(d[col], errors="coerce", utc=True)
            .dt.tz_convert("UTC")
            .dt.tz_localize(None)
        )
        return d.dropna(subset=[col])

    @staticmethod
    def month_start(now: pd.Timestamp | None = None) -> pd.Timestamp:
        ts = (now or pd.Timestamp.utcnow()).tz_localize(None)
        return pd.Timestamp(year=ts.year, month=ts.month, day=1)

    @staticmethod
    def scoped(df: pd.DataFrame, client_id: str | None) -> pd.DataFrame:
        if df.empty or client_id in (None, "") or "client_id" not in df.columns:
            return df.copy()
        return df[df["client_id"] == client_id].copy()

    def apply_date_range(
        self, df: pd.DataFrame, date_range: DateRange | None, col: str = "timestamp"
    ) -> pd.DataFrame:
        d = self.parse_timestamp(df, col)
        if d.empty or date_range is None:
            return d
        start = pd.Timestamp(date_range.start).tz_localize(None)
        end = pd.Timestamp(date_range.end).tz_localize(None)
        end = max(end, end.normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
        return d[(d[col] >= start) & (d[col] <= end)].copy()

    @staticmethod
    def _is_uuid(value: str) -> bool:
        try:
            uuid.UUID(str(value))
            return True
        except Exception:
            return False

    def last_n_days_range(self, days: int) -> DateRange:
        end = pd.Timestamp.utcnow().tz_localize(None)
        start = end - pd.Timedelta(days=days)
        return DateRange(start=start, end=end)

    def _product_map(self, client_id: str | None) -> pd.DataFrame:
        products = self.scoped(self.products.all(), client_id)
        if products.empty:
            return pd.DataFrame(columns=["product_id", "product_name"])
        return products[["product_id", "product_name"]].drop_duplicates()

    def revenue(self, client_id: str | None, date_range: DateRange | None = None) -> float:
        orders = self.apply_date_range(self.scoped(self.orders.all(), client_id), date_range)
        if orders.empty:
            return 0.0
        confirmed = orders[orders["status"].fillna("") == "confirmed"].copy()
        if confirmed.empty:
            return 0.0
        confirmed["grand_total"] = self.to_float(
            confirmed.get("grand_total", pd.Series(dtype=float))
        )
        return float(confirmed["grand_total"].sum())

    def expenses(self, client_id: str | None, date_range: DateRange | None = None) -> float:
        ledger = self.apply_date_range(self.scoped(self.ledger.all(), client_id), date_range)
        if ledger.empty:
            return 0.0
        ledger["amount"] = self.to_float(ledger["amount"])
        return float(ledger[ledger["entry_type"] == "expense"]["amount"].sum())

    def cogs(self, client_id: str | None, date_range: DateRange | None = None) -> float:
        inv = self.apply_date_range(self.scoped(self.inv.all(), client_id), date_range)
        if inv.empty:
            return 0.0
        inv["total_cost"] = self.to_float(inv.get("total_cost", pd.Series(dtype=float)))
        return float(inv[inv["txn_type"] == "OUT"]["total_cost"].sum())

    def profit(self, client_id: str | None, date_range: DateRange | None = None) -> float:
        return float(
            self.revenue(client_id, date_range)
            - self.expenses(client_id, date_range)
            - self.cogs(client_id, date_range)
        )

    def orders_count(self, client_id: str | None, date_range: DateRange | None = None) -> float:
        orders = self.apply_date_range(self.scoped(self.orders.all(), client_id), date_range)
        if orders.empty:
            return 0.0
        return float(len(orders[orders["status"].fillna("") == "confirmed"]))

    def sold_qty(self, client_id: str | None, date_range: DateRange | None = None) -> float:
        orders = self.apply_date_range(self.scoped(self.orders.all(), client_id), date_range)
        if orders.empty:
            return 0.0
        confirmed = orders[orders["status"].fillna("") == "confirmed"][["order_id"]]
        if confirmed.empty:
            return 0.0
        items = self.order_items.all()
        if items.empty:
            return 0.0
        d = items.merge(confirmed, on="order_id", how="inner")
        if d.empty:
            return 0.0
        d["qty"] = self.to_float(d["qty"])
        return float(d["qty"].sum())

    def aov(self, client_id: str | None, date_range: DateRange | None = None) -> float:
        cnt = self.orders_count(client_id, date_range)
        return float(self.revenue(client_id, date_range) / cnt) if cnt else 0.0

    def outstanding_invoices_amount(
        self, client_id: str | None, date_range: DateRange | None = None
    ) -> float:
        invoices = self.scoped(self.invoices.all(), client_id)
        if invoices.empty:
            return 0.0
        if date_range is not None:
            invoices = self.apply_date_range(invoices, date_range)
        if invoices.empty:
            return 0.0
        invoices = invoices[invoices["status"].isin(["unpaid", "partial"])].copy()
        if invoices.empty:
            return 0.0
        invoices["amount_due"] = self.to_float(invoices["amount_due"])
        payments = self.scoped(self.payments.all(), client_id)
        if payments.empty:
            return float(invoices["amount_due"].sum())
        payments["amount_paid"] = self.to_float(payments["amount_paid"])
        paid = payments.groupby("invoice_id", as_index=False).agg(total_paid=("amount_paid", "sum"))
        out = invoices.merge(paid, on="invoice_id", how="left")
        out["total_paid"] = out["total_paid"].fillna(0.0)
        out["outstanding"] = (out["amount_due"] - out["total_paid"]).clip(lower=0.0)
        return float(out["outstanding"].sum())

    def current_stock_qty_by_product(self, client_id: str | None) -> pd.DataFrame:
        inv = self.reconciliation.normalized_inventory_rows(client_id)
        if inv.empty:
            return pd.DataFrame(columns=["product_id", "product_name", "current_qty"])
        inv["signed_qty"] = inv.apply(
            lambda r: r["qty"] if r["txn_type"] in {"IN", "ADJUST+", "ADJUST"} else -r["qty"],
            axis=1,
        )
        stock = (
            inv.groupby("canonical_product_id", as_index=False)
            .agg(current_qty=("signed_qty", "sum"))
            .rename(columns={"canonical_product_id": "product_id"})
        )
        return stock.merge(self._product_map(client_id), on="product_id", how="left")

    def current_stock_value_by_product(self, client_id: str | None) -> pd.DataFrame:
        inv = self.reconciliation.normalized_inventory_rows(client_id)
        if inv.empty:
            return pd.DataFrame(columns=["product_id", "product_name", "stock_value"])
        inv["signed_qty"] = inv.apply(
            lambda r: r["qty"] if r["txn_type"] in {"IN", "ADJUST+", "ADJUST"} else -r["qty"],
            axis=1,
        )
        lots = inv.groupby(["canonical_product_id", "lot_id"], as_index=False).agg(
            current_qty=("signed_qty", "sum"), unit_cost=("unit_cost", "last")
        )
        lots = lots[lots["current_qty"] > 0].copy()
        lots["stock_value"] = lots["current_qty"] * lots["unit_cost"]
        d = (
            lots.groupby("canonical_product_id", as_index=False)
            .agg(stock_value=("stock_value", "sum"))
            .rename(columns={"canonical_product_id": "product_id"})
        )
        d = d.merge(self._product_map(client_id), on="product_id", how="left")
        d["product_name"] = d["product_name"].fillna(d["product_id"])
        return d.sort_values("stock_value", ascending=False)

    def product_aging(self, client_id: str | None) -> pd.DataFrame:
        inv = self.reconciliation.normalized_inventory_rows(client_id)
        if inv.empty:
            return pd.DataFrame(
                columns=[
                    "product_id",
                    "product_name",
                    "total_in_qty",
                    "current_qty",
                    "sold_qty",
                    "sold_pct",
                    "remaining_pct",
                ]
            )
        total_in = (
            inv[inv["txn_type"] == "IN"]
            .groupby("canonical_product_id", as_index=False)
            .agg(total_in_qty=("qty", "sum"))
        )
        current = self.current_stock_qty_by_product(client_id).rename(
            columns={"product_id": "product_key"}
        )
        total_in = total_in.rename(columns={"canonical_product_id": "product_key"})
        d = total_in.merge(current[["product_key", "current_qty"]], on="product_key", how="left")
        d["current_qty"] = d["current_qty"].fillna(0.0)
        d = d[d["total_in_qty"] > 0]
        d["sold_qty"] = (d["total_in_qty"] - d["current_qty"]).clip(lower=0)
        d["sold_pct"] = (d["sold_qty"] / d["total_in_qty"]).clip(lower=0, upper=1) * 100
        d["remaining_pct"] = (d["current_qty"] / d["total_in_qty"]).clip(lower=0, upper=1) * 100
        d = d.rename(columns={"product_key": "product_id"}).merge(
            self._product_map(client_id), on="product_id", how="left"
        )
        d["product_name"] = d["product_name"].fillna(d["product_id"])
        return d

    def margin_by_product(
        self, client_id: str | None, date_range: DateRange | None = None
    ) -> pd.DataFrame:
        items = self.order_items.all()
        orders = self.apply_date_range(self.scoped(self.orders.all(), client_id), date_range)
        if items.empty or orders.empty:
            return pd.DataFrame(
                columns=["product_id", "product_name", "revenue", "cogs", "margin_pct"]
            )
        valid_orders = orders[orders["status"].fillna("") == "confirmed"][
            ["order_id"]
        ].drop_duplicates()
        s = items.merge(valid_orders, on="order_id", how="inner")
        s["total_selling_price"] = self.to_float(s["total_selling_price"])
        s = s.groupby("product_id", as_index=False).agg(revenue=("total_selling_price", "sum"))

        inv = self.apply_date_range(
            self.reconciliation.normalized_inventory_rows(client_id), date_range
        )
        inv["total_cost"] = self.to_float(inv["total_cost"])
        c = (
            inv[inv["txn_type"] == "OUT"]
            .groupby("canonical_product_id", as_index=False)
            .agg(cogs=("total_cost", "sum"))
            .rename(columns={"canonical_product_id": "product_id"})
        )
        d = s.merge(c, on="product_id", how="left")
        d["cogs"] = d["cogs"].fillna(0.0)
        d["margin_pct"] = ((d["revenue"] - d["cogs"]) / d["revenue"].replace(0, pd.NA)).fillna(
            0.0
        ) * 100
        d = d.merge(self._product_map(client_id), on="product_id", how="left")
        d["product_name"] = d["product_name"].fillna(d["product_id"])
        return d

    def sell_speed_by_product(self, client_id: str | None, days: int = 30) -> pd.DataFrame:
        rng = self.last_n_days_range(days)
        inv = self.apply_date_range(self.reconciliation.normalized_inventory_rows(client_id), rng)
        if inv.empty:
            return pd.DataFrame(
                columns=["product_id", "sell_speed_units_per_day", "units_sold_last_30d"]
            )
        sold = (
            inv[inv["txn_type"] == "OUT"]
            .groupby("canonical_product_id", as_index=False)
            .agg(units_sold_last_30d=("qty", "sum"))
            .rename(columns={"canonical_product_id": "product_id"})
        )
        sold["sell_speed_units_per_day"] = sold["units_sold_last_30d"] / float(days)
        sold = sold.merge(self._product_map(client_id), on="product_id", how="left")
        sold["product_name"] = sold["product_name"].fillna(sold["product_id"])
        return sold

    def lot_profit_recovery(self, client_id: str | None) -> pd.DataFrame:
        inv = self.reconciliation.normalized_inventory_rows(client_id)
        if inv.empty:
            return pd.DataFrame(columns=["lot_id", "product_id", "total_cost", "recovered_revenue"])
        inv["qty"] = self.to_float(inv["qty"])
        inv["total_cost"] = self.to_float(inv["total_cost"])

        in_lots = (
            inv[inv["txn_type"] == "IN"]
            .groupby(["lot_id", "canonical_product_id"], as_index=False)
            .agg(total_cost=("total_cost", "sum"))
            .rename(columns={"canonical_product_id": "product_id"})
        )
        out_lots = inv[inv["txn_type"] == "OUT"][
            ["lot_id", "canonical_product_id", "source_id", "qty"]
        ].rename(columns={"canonical_product_id": "product_id"})
        if out_lots.empty:
            in_lots["recovered_revenue"] = 0.0
            return in_lots

        items = self.order_items.all().copy()
        if items.empty:
            in_lots["recovered_revenue"] = 0.0
            return in_lots
        items["qty"] = self.to_float(items["qty"])
        items["total_selling_price"] = self.to_float(items["total_selling_price"])
        items = items.rename(columns={"order_id": "source_id", "qty": "sold_qty"})

        alloc = out_lots.merge(
            items[["source_id", "product_id", "sold_qty", "total_selling_price"]],
            on=["source_id", "product_id"],
            how="left",
        )
        alloc["sold_qty"] = alloc["sold_qty"].fillna(0.0)
        alloc["price_per_unit"] = alloc["total_selling_price"] / alloc["sold_qty"].replace(0, pd.NA)
        alloc["allocated_revenue"] = alloc["qty"] * alloc["price_per_unit"].fillna(0.0)
        rev = alloc.groupby(["lot_id", "product_id"], as_index=False).agg(
            recovered_revenue=("allocated_revenue", "sum")
        )
        d = in_lots.merge(rev, on=["lot_id", "product_id"], how="left")
        d["recovered_revenue"] = d["recovered_revenue"].fillna(0.0)
        return d

    def revenue_trend(
        self, client_id: str | None, granularity: Granularity, date_range: DateRange
    ) -> pd.DataFrame:
        d = self.apply_date_range(self.scoped(self.orders.all(), client_id), date_range)
        if d.empty:
            return pd.DataFrame(columns=["period", "revenue"])
        d = d[d["status"].fillna("") == "confirmed"].copy()
        d["amount"] = self.to_float(d["grand_total"])
        d["period"] = d["timestamp"].dt.to_period(granularity).dt.to_timestamp()
        return (
            d.groupby("period", as_index=False).agg(revenue=("amount", "sum")).sort_values("period")
        )

    def income_vs_expense_trend(
        self, client_id: str | None, granularity: Granularity, date_range: DateRange
    ) -> pd.DataFrame:
        d = self.apply_date_range(self.scoped(self.ledger.all(), client_id), date_range)
        if d.empty:
            return pd.DataFrame(columns=["period", "income", "expense", "profit"])
        d["amount"] = self.to_float(d["amount"])
        d["period"] = d["timestamp"].dt.to_period(granularity).dt.to_timestamp()
        trend = d.pivot_table(
            index="period", columns="entry_type", values="amount", aggfunc="sum", fill_value=0.0
        ).reset_index()
        trend.columns.name = None
        trend["earning"] = trend.get("earning", 0.0)
        trend["expense"] = trend.get("expense", 0.0)
        trend = trend.rename(columns={"earning": "income"})
        trend["profit"] = trend["income"] - trend["expense"]
        return trend[["period", "income", "expense", "profit"]].sort_values("period")

    def integrity_warnings(self, client_id: str | None) -> list[str]:
        warnings: list[str] = []
        inv = self.scoped(self.inv.all(), client_id)
        if not inv.empty:
            inv["qty_num"] = pd.to_numeric(inv.get("qty", 0), errors="coerce")
            inv["total_cost_num"] = pd.to_numeric(inv.get("total_cost", 0), errors="coerce")
            coerced = int(inv["total_cost_num"].isna().sum() + inv["qty_num"].isna().sum())
            if coerced:
                warnings.append(f"{coerced} non-numeric qty/cost values were coerced to zero.")
            inv["qty"] = inv["qty_num"].fillna(0.0)
            inv["signed_qty"] = inv.apply(
                lambda r: r["qty"] if r["txn_type"] == "IN" else -r["qty"], axis=1
            )
            stock = inv.groupby(["product_id", "lot_id"], as_index=False).agg(
                current_qty=("signed_qty", "sum")
            )
            if not stock[stock["current_qty"] < 0].empty:
                warnings.append("Negative stock detected for one or more product lots.")
            if not inv[
                (inv["txn_type"] == "OUT") & (inv["lot_id"].astype(str).str.strip() == "")
            ].empty:
                warnings.append("OUT transactions with missing lot_id detected.")
        issues = self.reconciliation.integrity_issues(client_id)
        inventory_unmapped_count = len(
            [i for i in issues if i.issue_type == "inventory_unmapped_product"]
        )
        if inventory_unmapped_count:
            warnings.append(f"{inventory_unmapped_count} inventory rows have unmapped product_id.")
        if any(i.issue_type == "orphan_ledger_earning" for i in issues):
            warnings.append("Ledger earning rows exist without matching sales order.")
        if any(i.issue_type == "sales_order_without_items" for i in issues):
            warnings.append("Confirmed sales orders without items detected.")

        products = self._product_map(client_id)
        product_ids = (
            set(products["product_id"].astype(str).tolist()) if not products.empty else set()
        )
        items = self.order_items.all()
        orders = self.scoped(self.orders.all(), client_id)
        if not items.empty and not orders.empty and product_ids:
            scoped_items = items.merge(orders[["order_id"]], on="order_id", how="inner")
            missing = scoped_items[~scoped_items["product_id"].astype(str).isin(product_ids)]
            if not missing.empty:
                warnings.append(f"{len(missing)} sales order items have unknown product_id.")
        return warnings

    def integrity_issues(self, client_id: str | None) -> list[dict[str, str]]:
        return [
            {
                "issue_type": i.issue_type,
                "severity": i.severity,
                "client_id": i.client_id,
                "reference_id": i.reference_id,
                "message": i.message,
            }
            for i in self.reconciliation.integrity_issues(client_id)
        ]
