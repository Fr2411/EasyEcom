from __future__ import annotations

import pandas as pd

from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, SalesOrderItemsRepo, SalesOrdersRepo


class DashboardService:
    @staticmethod
    def _naive_ts(value: pd.Timestamp | str) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        return ts.tz_localize(None) if ts.tzinfo is not None else ts

    def __init__(
        self,
        inv: InventoryTxnRepo,
        ledger: LedgerRepo,
        orders: SalesOrdersRepo,
        invoices: InvoicesRepo,
        order_items: SalesOrderItemsRepo,
        products: ProductsRepo,
        clients: ClientsRepo,
    ):
        self.inv = inv
        self.ledger = ledger
        self.orders = orders
        self.invoices = invoices
        self.order_items = order_items
        self.products = products
        self.clients = clients

    @staticmethod
    def _scope(df: pd.DataFrame, client_id: str | None) -> pd.DataFrame:
        if df.empty or client_id in (None, ""):
            return df.copy()
        return df[df["client_id"] == client_id].copy()

    @staticmethod
    def _to_num(series: pd.Series) -> pd.Series:
        return pd.to_numeric(series, errors="coerce").fillna(0.0)

    @staticmethod
    def _month_start() -> pd.Timestamp:
        now = pd.Timestamp.utcnow().tz_localize(None)
        return pd.Timestamp(year=now.year, month=now.month, day=1)

    @staticmethod
    def _normalize_ts(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "timestamp" not in df.columns:
            return df
        d = df.copy()
        d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce", utc=True).dt.tz_localize(
            None
        )
        return d.dropna(subset=["timestamp"])

    def _product_map(self, client_id: str | None) -> pd.DataFrame:
        products = self._scope(self.products.all(), client_id)
        if products.empty:
            return pd.DataFrame(columns=["product_id", "product_name"])
        return products[["product_id", "product_name"]].drop_duplicates()

    def _inventory_with_stock(self, client_id: str | None) -> pd.DataFrame:
        inv = self._scope(self.inv.all(), client_id)
        if inv.empty:
            return pd.DataFrame(
                columns=["product_id", "lot_id", "current_qty", "unit_cost", "stock_value"]
            )
        inv["qty"] = self._to_num(inv["qty"])
        inv["unit_cost"] = self._to_num(inv["unit_cost"])
        inv["signed_qty"] = inv.apply(
            lambda r: r["qty"] if r["txn_type"] == "IN" else -r["qty"], axis=1
        )
        lots = inv.groupby(["product_id", "lot_id"], as_index=False).agg(
            current_qty=("signed_qty", "sum"), unit_cost=("unit_cost", "last")
        )
        lots["stock_value"] = lots["current_qty"] * lots["unit_cost"]
        return lots

    def kpis(self, client_id: str | None) -> dict[str, float]:
        month_start = self._month_start()
        lots = self._inventory_with_stock(client_id)
        stock_value = (
            float(lots[lots["current_qty"] > 0]["stock_value"].sum()) if not lots.empty else 0.0
        )

        ledger = self._normalize_ts(self._scope(self.ledger.all(), client_id))
        revenue = expenses = 0.0
        if not ledger.empty:
            ledger["amount"] = self._to_num(ledger["amount"])
            ledger_mtd = ledger[ledger["timestamp"] >= month_start]
            revenue = float(ledger_mtd[ledger_mtd["entry_type"] == "earning"]["amount"].sum())
            expenses = float(ledger_mtd[ledger_mtd["entry_type"] == "expense"]["amount"].sum())

        orders = self._normalize_ts(self._scope(self.orders.all(), client_id))
        orders_mtd = 0.0
        aov = 0.0
        if not orders.empty:
            orders["grand_total"] = self._to_num(orders["grand_total"])
            o_mtd = orders[orders["timestamp"] >= month_start]
            orders_mtd = float(len(o_mtd))
            if orders_mtd:
                aov = float(o_mtd["grand_total"].mean())

        invoices = self._scope(self.invoices.all(), client_id)
        outstanding = 0.0
        if not invoices.empty:
            i = invoices[invoices["status"] != "paid"].copy()
            i["amount_due"] = self._to_num(i["amount_due"])
            outstanding = float(i["amount_due"].sum())

        return {
            "Current Stock Value": stock_value,
            "Revenue MTD": revenue,
            "Expenses MTD": expenses,
            "Profit MTD": revenue - expenses,
            "Orders MTD": orders_mtd,
            "AOV MTD": aov,
            "Outstanding Invoices": outstanding,
        }

    def revenue_trend(
        self, client_id: str | None, freq: str, start_date: pd.Timestamp, end_date: pd.Timestamp
    ) -> pd.DataFrame:
        ledger = self._normalize_ts(self._scope(self.ledger.all(), client_id))
        if ledger.empty:
            return pd.DataFrame(columns=["period", "revenue"])
        d = ledger[ledger["entry_type"] == "earning"].copy()
        d["amount"] = self._to_num(d["amount"])
        start = self._naive_ts(start_date)
        end = self._naive_ts(end_date)
        d = d[(d["timestamp"] >= start) & (d["timestamp"] <= end)]
        if d.empty:
            return pd.DataFrame(columns=["period", "revenue"])
        d["period"] = d["timestamp"].dt.to_period(freq).dt.to_timestamp()
        return (
            d.groupby("period", as_index=False).agg(revenue=("amount", "sum")).sort_values("period")
        )

    def stock_value_by_product(self, client_id: str | None) -> pd.DataFrame:
        lots = self._inventory_with_stock(client_id)
        if lots.empty:
            return pd.DataFrame(columns=["product_id", "stock_value", "product_name"])
        d = (
            lots[lots["current_qty"] > 0]
            .groupby("product_id", as_index=False)
            .agg(stock_value=("stock_value", "sum"))
        )
        d = d.merge(self._product_map(client_id), on="product_id", how="left")
        d["product_name"] = d["product_name"].fillna(d["product_id"])
        return d.sort_values("stock_value", ascending=False)

    def product_aging(self, client_id: str | None) -> pd.DataFrame:
        inv = self._scope(self.inv.all(), client_id)
        if inv.empty:
            return pd.DataFrame(columns=["product_id", "sold_pct", "remaining_pct", "product_name"])
        inv["qty"] = self._to_num(inv["qty"])
        in_qty = (
            inv[inv["txn_type"] == "IN"]
            .groupby("product_id", as_index=False)
            .agg(total_in_qty=("qty", "sum"))
        )
        lots = (
            self._inventory_with_stock(client_id)
            .groupby("product_id", as_index=False)
            .agg(current_qty=("current_qty", "sum"))
        )
        d = in_qty.merge(lots, on="product_id", how="left")
        d["current_qty"] = d["current_qty"].fillna(0.0)
        d = d[d["total_in_qty"] > 0]
        d["sold_pct"] = ((d["total_in_qty"] - d["current_qty"]) / d["total_in_qty"]).clip(
            lower=0, upper=1
        ) * 100
        d["remaining_pct"] = (d["current_qty"] / d["total_in_qty"]).clip(lower=0, upper=1) * 100
        d = d.merge(self._product_map(client_id), on="product_id", how="left")
        d["product_name"] = d["product_name"].fillna(d["product_id"])
        return d.sort_values("sold_pct", ascending=False)

    def margin_sell_speed(self, client_id: str | None) -> pd.DataFrame:
        items = self.order_items.all()
        orders = self._normalize_ts(self._scope(self.orders.all(), client_id))
        inv = self._scope(self.inv.all(), client_id)
        if items.empty or orders.empty:
            return pd.DataFrame(
                columns=["product_id", "margin_pct", "sell_speed", "revenue", "product_name"]
            )

        orders = orders[["order_id", "timestamp", "client_id"]]
        items = items.merge(orders, on="order_id", how="inner")
        if client_id not in (None, ""):
            items = items[items["client_id"] == client_id]
        if items.empty:
            return pd.DataFrame(
                columns=["product_id", "margin_pct", "sell_speed", "revenue", "product_name"]
            )

        items["qty"] = self._to_num(items["qty"])
        items["total_selling_price"] = self._to_num(items["total_selling_price"])
        sales = items.groupby("product_id", as_index=False).agg(
            units_sold=("qty", "sum"),
            revenue=("total_selling_price", "sum"),
            avg_selling_price=(
                "total_selling_price",
                lambda s: s.sum() / max(items.loc[s.index, "qty"].sum(), 1),
            ),
        )

        out_txn = inv[inv["txn_type"] == "OUT"].copy()
        if out_txn.empty:
            sales["avg_cogs"] = 0.0
        else:
            out_txn["qty"] = self._to_num(out_txn["qty"])
            out_txn["total_cost"] = self._to_num(out_txn["total_cost"])
            cogs = out_txn.groupby("product_id", as_index=False).agg(
                total_qty=("qty", "sum"), total_cogs=("total_cost", "sum")
            )
            cogs["avg_cogs"] = cogs["total_cogs"] / cogs["total_qty"].replace(0, 1)
            sales = sales.merge(cogs[["product_id", "avg_cogs"]], on="product_id", how="left")
            sales["avg_cogs"] = sales["avg_cogs"].fillna(0.0)

        first_stock = self._normalize_ts(inv[inv["txn_type"] == "IN"].copy())
        if first_stock.empty:
            sales["sell_speed"] = 0.0
        else:
            fs = first_stock.groupby("product_id", as_index=False).agg(
                first_stocked=("timestamp", "min")
            )
            sales = sales.merge(fs, on="product_id", how="left")
            now = pd.Timestamp.utcnow().tz_localize(None)
            sales["days_since_first_stock"] = (
                (now - sales["first_stocked"]).dt.days.clip(lower=1).fillna(30)
            )
            sales["sell_speed"] = sales["units_sold"] / sales["days_since_first_stock"]

        sales["margin_pct"] = (
            (sales["avg_selling_price"] - sales["avg_cogs"])
            / sales["avg_selling_price"].replace(0, pd.NA)
        ).fillna(0.0) * 100
        sales = sales.merge(self._product_map(client_id), on="product_id", how="left")
        sales["product_name"] = sales["product_name"].fillna(sales["product_id"])
        return sales[
            ["product_id", "product_name", "margin_pct", "sell_speed", "revenue"]
        ].sort_values("revenue", ascending=False)

    def income_expense_trend(
        self, client_id: str | None, freq: str, start_date: pd.Timestamp, end_date: pd.Timestamp
    ) -> pd.DataFrame:
        ledger = self._normalize_ts(self._scope(self.ledger.all(), client_id))
        if ledger.empty:
            return pd.DataFrame(columns=["period", "income", "expense"])
        ledger["amount"] = self._to_num(ledger["amount"])
        start = self._naive_ts(start_date)
        end = self._naive_ts(end_date)
        d = ledger[(ledger["timestamp"] >= start) & (ledger["timestamp"] <= end)].copy()
        if d.empty:
            return pd.DataFrame(columns=["period", "income", "expense"])
        d["period"] = d["timestamp"].dt.to_period(freq).dt.to_timestamp()
        trend = d.pivot_table(
            index="period", columns="entry_type", values="amount", aggfunc="sum", fill_value=0.0
        ).reset_index()
        trend.columns.name = None
        if "earning" not in trend.columns:
            trend["earning"] = 0.0
        if "expense" not in trend.columns:
            trend["expense"] = 0.0
        trend = trend.rename(columns={"earning": "income"})
        return trend[["period", "income", "expense"]].sort_values("period")

    def lot_profitability(self, client_id: str | None) -> pd.DataFrame:
        inv = self._scope(self.inv.all(), client_id)
        if inv.empty:
            return pd.DataFrame(columns=["lot_id", "product_id", "total_cost", "recovered_revenue"])

        inv["qty"] = self._to_num(inv["qty"])
        inv["total_cost"] = self._to_num(inv["total_cost"])
        in_lots = (
            inv[inv["txn_type"] == "IN"]
            .groupby(["lot_id", "product_id"], as_index=False)
            .agg(total_cost=("total_cost", "sum"))
        )

        out_lots = inv[inv["txn_type"] == "OUT"].copy()
        if out_lots.empty:
            in_lots["recovered_revenue"] = 0.0
            return in_lots

        out_lots = out_lots[["lot_id", "product_id", "source_id", "qty"]]
        items = self.order_items.all()[["order_id", "product_id", "qty", "total_selling_price"]]
        items["qty"] = self._to_num(items["qty"])
        items["total_selling_price"] = self._to_num(items["total_selling_price"])
        items = items.rename(columns={"order_id": "source_id", "qty": "sold_qty"})
        alloc = out_lots.merge(items, on=["source_id", "product_id"], how="left")
        alloc["sold_qty"] = self._to_num(alloc["sold_qty"])
        alloc["price_per_unit"] = alloc["total_selling_price"] / alloc["sold_qty"].replace(0, pd.NA)
        alloc["allocated_revenue"] = alloc["qty"] * alloc["price_per_unit"].fillna(0.0)
        rev = alloc.groupby(["lot_id", "product_id"], as_index=False).agg(
            recovered_revenue=("allocated_revenue", "sum")
        )
        d = in_lots.merge(rev, on=["lot_id", "product_id"], how="left")
        d["recovered_revenue"] = d["recovered_revenue"].fillna(0.0)
        return d.sort_values("total_cost", ascending=False)

    def revenue_by_client(self) -> pd.DataFrame:
        ledger = self._scope(self.ledger.all(), None)
        if ledger.empty:
            return pd.DataFrame(columns=["client_id", "revenue", "business_name"])
        ledger = ledger[ledger["entry_type"] == "earning"].copy()
        ledger["amount"] = self._to_num(ledger["amount"])
        d = ledger.groupby("client_id", as_index=False).agg(revenue=("amount", "sum"))
        return d.merge(
            self.clients.all()[["client_id", "business_name"]], on="client_id", how="left"
        )

    def inventory_value_by_client(self) -> pd.DataFrame:
        inv = self.inv.all()
        if inv.empty:
            return pd.DataFrame(columns=["client_id", "stock_value", "business_name"])
        inv["qty"] = self._to_num(inv["qty"])
        inv["unit_cost"] = self._to_num(inv["unit_cost"])
        inv["signed_qty"] = inv.apply(
            lambda r: r["qty"] if r["txn_type"] == "IN" else -r["qty"], axis=1
        )
        lots = inv.groupby(["client_id", "product_id", "lot_id"], as_index=False).agg(
            current_qty=("signed_qty", "sum"), unit_cost=("unit_cost", "last")
        )
        lots = lots[lots["current_qty"] > 0]
        lots["stock_value"] = lots["current_qty"] * lots["unit_cost"]
        d = lots.groupby("client_id", as_index=False).agg(stock_value=("stock_value", "sum"))
        return d.merge(
            self.clients.all()[["client_id", "business_name"]], on="client_id", how="left"
        )

    def client_health_flags(self) -> pd.DataFrame:
        now = pd.Timestamp.utcnow().tz_localize(None)
        inv = self._normalize_ts(self.inv.all())
        orders = self._normalize_ts(self.orders.all())
        clients = self.clients.all()[["client_id", "business_name"]]
        if clients.empty:
            return pd.DataFrame(columns=["client_id", "business_name", "flags"])

        negative_stock_clients: set[str] = set()
        if not inv.empty:
            inv["qty"] = self._to_num(inv["qty"])
            inv["signed_qty"] = inv.apply(
                lambda r: r["qty"] if r["txn_type"] == "IN" else -r["qty"], axis=1
            )
            stock = inv.groupby(["client_id", "product_id", "lot_id"], as_index=False).agg(
                current_qty=("signed_qty", "sum")
            )
            negative_stock_clients = set(stock[stock["current_qty"] < 0]["client_id"].unique())

        inactive_clients: set[str] = set(clients["client_id"])
        if not orders.empty:
            recent_cutoff = now - pd.Timedelta(days=14)
            active = set(orders[orders["timestamp"] >= recent_cutoff]["client_id"].unique())
            inactive_clients = set(clients["client_id"]) - active

        rows: list[dict[str, str]] = []
        for _, c in clients.iterrows():
            flags: list[str] = []
            cid = c["client_id"]
            if cid in negative_stock_clients:
                flags.append("negative_stock")
            if cid in inactive_clients:
                flags.append("no_activity_14d")
            rows.append(
                {
                    "client_id": cid,
                    "business_name": c["business_name"],
                    "flags": ", ".join(flags) if flags else "healthy",
                }
            )
        return pd.DataFrame(rows)
