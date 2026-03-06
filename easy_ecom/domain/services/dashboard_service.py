from __future__ import annotations

import pandas as pd

from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
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
from easy_ecom.domain.services.metrics_service import DateRange, MetricsService


class DashboardService:
    def __init__(
        self,
        inv: InventoryTxnRepo,
        ledger: LedgerRepo,
        orders: SalesOrdersRepo,
        invoices: InvoicesRepo,
        order_items: SalesOrderItemsRepo,
        products: ProductsRepo,
        variants: ProductVariantsRepo,
        clients: ClientsRepo,
        payments: PaymentsRepo | None = None,
    ):
        self.clients = clients
        self.metrics = MetricsService(
            inv,
            ledger,
            orders,
            invoices,
            payments or PaymentsRepo(inv.store),
            order_items,
            products,
            variants,
        )

    @staticmethod
    def _safe_pct(numerator: float, denominator: float) -> float:
        return float((numerator / denominator) * 100.0) if denominator else 0.0

    def _data_health_score(self, client_id: str | None) -> float:
        score = self.reconciliation_health_scorecard(client_id)
        total_flags = float(
            score.get("orphan_ledger_sale_earnings", 0)
            + score.get("confirmed_sales_missing_items", 0)
            + score.get("truly_broken_sales_item_identities", 0)
            + score.get("unmapped_inventory_rows", 0)
            + score.get("client_mismatch_issues", 0)
        )
        health = max(0.0, 100.0 - (total_flags * 5.0))
        return float(round(health, 1))

    def business_health_snapshot(self, client_id: str | None) -> dict[str, float]:
        mtd = DateRange(
            start=self.metrics.month_start(), end=pd.Timestamp.utcnow().tz_localize(None)
        )
        revenue = self.metrics.revenue(client_id, mtd)
        cogs = self.metrics.cogs(client_id, mtd)
        gross_profit = revenue - cogs
        expenses = self.metrics.expenses(client_id, mtd)
        net_operating_profit = gross_profit - expenses
        inventory_value = float(
            self.metrics.current_stock_value_by_product(client_id)["stock_value"].sum()
        )
        outstanding_receivables = self.metrics.outstanding_invoices_amount(client_id)
        gross_margin_pct = self._safe_pct(gross_profit, revenue)
        return {
            "Revenue": float(revenue),
            "Gross Profit": float(gross_profit),
            "Net Operating Profit": float(net_operating_profit),
            "Gross Margin %": float(gross_margin_pct),
            "Inventory Value": float(inventory_value),
            "Outstanding Receivables": float(outstanding_receivables),
            "Data Health Score": float(self._data_health_score(client_id)),
        }

    def kpis(self, client_id: str | None) -> dict[str, float]:
        """Backward-compatible KPI facade used by tests and older UI flows."""
        snapshot = self.business_health_snapshot(client_id)
        mtd = DateRange(
            start=self.metrics.month_start(), end=pd.Timestamp.utcnow().tz_localize(None)
        )
        revenue = snapshot["Revenue"]
        gross_profit = snapshot["Gross Profit"]
        expenses = self.metrics.expenses(client_id, mtd)
        return {
            "Current Stock Value": snapshot["Inventory Value"],
            "Revenue MTD": revenue,
            "COGS MTD": self.metrics.cogs(client_id, mtd),
            "Gross Profit MTD": gross_profit,
            "Expenses MTD": expenses,
            "Net Operating Profit MTD": snapshot["Net Operating Profit"],
            "Sold Qty MTD": self.metrics.sold_qty(client_id, mtd),
            "Orders MTD": self.metrics.orders_count(client_id, mtd),
            "AOV MTD": self.metrics.aov(client_id, mtd),
            "Outstanding Invoices": snapshot["Outstanding Receivables"],
        }

    def trend_summary(
        self, client_id: str | None, freq: str, start_date: pd.Timestamp, end_date: pd.Timestamp
    ) -> pd.DataFrame:
        rng = DateRange(start_date, end_date)
        revenue = self.metrics.revenue_trend(client_id, freq, rng)
        inventory = self.metrics.inventory_value_trend(client_id, freq, rng)
        expense = self.metrics.expense_trend(client_id, freq, rng)
        periods = pd.DataFrame(
            {
                "period": pd.Index(
                    sorted(
                        set(revenue.get("period", pd.Series(dtype="datetime64[ns]")))
                        | set(inventory.get("period", pd.Series(dtype="datetime64[ns]")))
                        | set(expense.get("period", pd.Series(dtype="datetime64[ns]")))
                    )
                )
            }
        )
        if periods.empty:
            return pd.DataFrame(
                columns=[
                    "period",
                    "revenue",
                    "cogs",
                    "gross_profit",
                    "expenses",
                    "net_operating_profit",
                    "inventory_value",
                ]
            )
        trend = periods.merge(revenue, on="period", how="left").merge(
            inventory, on="period", how="left"
        )
        trend = trend.merge(expense, on="period", how="left")
        for col in ["revenue", "cogs", "gross_profit", "inventory_value", "expenses"]:
            if col not in trend.columns:
                trend[col] = 0.0
            trend[col] = trend[col].fillna(0.0)
        trend["net_operating_profit"] = trend["gross_profit"] - trend["expenses"]
        return trend.sort_values("period")

    def product_performance(self, client_id: str | None) -> dict[str, pd.DataFrame]:
        last_30 = self.metrics.last_n_days_range(30)
        margin = self.metrics.margin_by_product(client_id, last_30).copy()
        speed = self.metrics.sell_speed_by_product(client_id, days=30).copy()
        stock = self.metrics.current_stock_value_by_product(client_id).copy()
        combined = margin.merge(
            speed[["product_id", "sell_speed_units_per_day", "units_sold_last_30d"]],
            on="product_id",
            how="outer",
        ).merge(stock[["product_id", "stock_value"]], on="product_id", how="left")
        combined["product_name"] = combined["product_name"].fillna(combined["product_id"])
        combined[["revenue", "cogs", "margin_pct", "sell_speed_units_per_day", "units_sold_last_30d", "stock_value"]] = combined[["revenue", "cogs", "margin_pct", "sell_speed_units_per_day", "units_sold_last_30d", "stock_value"]].fillna(0.0)
        combined["gross_profit"] = combined["revenue"] - combined["cogs"]
        return {
            "top_revenue": combined.nlargest(10, "revenue"),
            "top_gross_profit": combined.nlargest(10, "gross_profit"),
            "lowest_margin": combined[combined["revenue"] > 0].nsmallest(10, "margin_pct"),
            "slow_moving": combined.nsmallest(10, "sell_speed_units_per_day"),
            "aging_dead_stock": combined[
                (combined["stock_value"] > 0) & (combined["units_sold_last_30d"] <= 0)
            ].nlargest(10, "stock_value"),
        }

    def inventory_health(self, client_id: str | None) -> dict[str, float | pd.DataFrame]:
        qty = self.metrics.current_stock_qty_by_product(client_id)
        value = self.metrics.current_stock_value_by_product(client_id)
        aging = self.metrics.product_aging(client_id)
        merged = qty.merge(value[["product_id", "stock_value"]], on="product_id", how="left")
        merged["stock_value"] = merged["stock_value"].fillna(0.0)
        low_stock = int(len(merged[(merged["current_qty"] > 0) & (merged["current_qty"] <= 5)]))
        out_of_stock = int(len(merged[merged["current_qty"] <= 0]))
        total = float(merged["stock_value"].sum()) if not merged.empty else 0.0
        top_share = float(merged.nlargest(5, "stock_value")["stock_value"].sum() / total * 100.0) if total else 0.0
        return {
            "current_stock_value": total,
            "low_stock_count": low_stock,
            "out_of_stock_count": out_of_stock,
            "top_5_stock_concentration_pct": top_share,
            "aging": aging,
            "sell_speed": self.metrics.sell_speed_by_product(client_id),
        }

    def financial_health(
        self, client_id: str | None, freq: str, start_date: pd.Timestamp, end_date: pd.Timestamp
    ) -> dict[str, float | pd.DataFrame]:
        rng = DateRange(start_date, end_date)
        outstanding = self.metrics.outstanding_invoices_amount(client_id)
        unpaid_confirmed = self.metrics.unpaid_confirmed_sales_amount(client_id)
        receivables_trend = self.metrics.receivables_trend(client_id, freq, rng)
        expense_trend = self.metrics.expense_trend(client_id, freq, rng)
        revenue_total = self.metrics.revenue(client_id, rng)
        expense_total = self.metrics.expenses(client_id, rng)
        return {
            "outstanding_invoices": float(outstanding),
            "unpaid_confirmed_sales": float(unpaid_confirmed),
            "expense_pressure_pct": self._safe_pct(expense_total, revenue_total),
            "receivables_trend": receivables_trend,
            "expense_trend": expense_trend,
        }

    def revenue_trend(
        self, client_id: str | None, freq: str, start_date: pd.Timestamp, end_date: pd.Timestamp
    ) -> pd.DataFrame:
        return self.metrics.revenue_trend(client_id, freq, DateRange(start_date, end_date))

    def stock_value_by_product(self, client_id: str | None) -> pd.DataFrame:
        return self.metrics.current_stock_value_by_product(client_id)

    def product_aging(self, client_id: str | None) -> pd.DataFrame:
        return self.metrics.product_aging(client_id)

    def margin_sell_speed(self, client_id: str | None) -> pd.DataFrame:
        m = self.metrics.margin_by_product(client_id, self.metrics.last_n_days_range(30))
        s = self.metrics.sell_speed_by_product(client_id, days=30)
        d = m.merge(
            s[["product_id", "sell_speed_units_per_day", "units_sold_last_30d"]],
            on="product_id",
            how="outer",
        )
        d["product_name"] = d["product_name"].fillna(d.get("product_id", ""))
        d["revenue_last_30d"] = d["revenue"].fillna(0.0)
        d["cogs_last_30d"] = d["cogs"].fillna(0.0)
        d["margin_pct"] = d["margin_pct"].fillna(0.0)
        d["sell_speed_units_per_day"] = d["sell_speed_units_per_day"].fillna(0.0)
        d["units_sold_last_30d"] = d["units_sold_last_30d"].fillna(0.0)
        return d[
            [
                "product_id",
                "product_name",
                "margin_pct",
                "sell_speed_units_per_day",
                "revenue_last_30d",
                "cogs_last_30d",
                "units_sold_last_30d",
            ]
        ].sort_values("revenue_last_30d", ascending=False)

    def income_expense_trend(
        self, client_id: str | None, freq: str, start_date: pd.Timestamp, end_date: pd.Timestamp
    ) -> pd.DataFrame:
        return self.metrics.income_vs_expense_trend(
            client_id, freq, DateRange(start_date, end_date)
        )

    def lot_profitability(self, client_id: str | None) -> pd.DataFrame:
        return self.metrics.lot_profit_recovery(client_id)

    def revenue_by_client(self) -> pd.DataFrame:
        rows = []
        for cid in self.clients.all().get("client_id", pd.Series(dtype=str)).tolist():
            rows.append({"client_id": cid, "revenue": self.metrics.revenue(cid)})
        d = pd.DataFrame(rows)
        if d.empty:
            return pd.DataFrame(columns=["client_id", "revenue", "business_name"])
        return d.merge(
            self.clients.all()[["client_id", "business_name"]], on="client_id", how="left"
        )

    def inventory_value_by_client(self) -> pd.DataFrame:
        rows = []
        for cid in self.clients.all().get("client_id", pd.Series(dtype=str)).tolist():
            stock = self.metrics.current_stock_value_by_product(cid)
            rows.append(
                {
                    "client_id": cid,
                    "stock_value": float(stock["stock_value"].sum()) if not stock.empty else 0.0,
                }
            )
        d = pd.DataFrame(rows)
        if d.empty:
            return pd.DataFrame(columns=["client_id", "stock_value", "business_name"])
        return d.merge(
            self.clients.all()[["client_id", "business_name"]], on="client_id", how="left"
        )

    def client_health_flags(self) -> pd.DataFrame:
        clients = self.clients.all()[["client_id", "business_name"]]
        rows = []
        for _, c in clients.iterrows():
            warnings = self.metrics.integrity_warnings(c["client_id"])
            rows.append(
                {
                    "client_id": c["client_id"],
                    "business_name": c["business_name"],
                    "flags": ", ".join(warnings) if warnings else "healthy",
                }
            )
        return pd.DataFrame(rows)

    def integrity_warnings(self, client_id: str | None) -> list[str]:
        return self.metrics.integrity_warnings(client_id)

    def integrity_issues(self, client_id: str | None) -> list[dict[str, str]]:
        return self.metrics.integrity_issues(client_id)

    def reconciliation_health_scorecard(self, client_id: str | None) -> dict[str, int]:
        return self.metrics.reconciliation_health_scorecard(client_id)
