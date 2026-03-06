from __future__ import annotations

import pandas as pd

from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
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
        )

    def kpis(self, client_id: str | None) -> dict[str, float]:
        mtd = DateRange(
            start=self.metrics.month_start(), end=pd.Timestamp.utcnow().tz_localize(None)
        )
        stock_value = float(
            self.metrics.current_stock_value_by_product(client_id)["stock_value"].sum()
        )
        revenue = self.metrics.revenue(client_id, mtd)
        expenses = self.metrics.expenses(client_id, mtd)
        return {
            "Current Stock Value": stock_value,
            "Revenue MTD": revenue,
            "Expenses MTD": expenses,
            "Profit MTD": self.metrics.profit(client_id, mtd),
            "Sold Qty MTD": self.metrics.sold_qty(client_id, mtd),
            "Orders MTD": self.metrics.orders_count(client_id, mtd),
            "AOV MTD": self.metrics.aov(client_id, mtd),
            "Outstanding Invoices": self.metrics.outstanding_invoices_amount(client_id),
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
