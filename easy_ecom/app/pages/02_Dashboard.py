import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.app.ui.formatters import format_money
from easy_ecom.core.config import settings
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
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.core.audit import log_event
from easy_ecom.data.repos.csv.audit_repo import AuditRepo
from easy_ecom.domain.services.dashboard_service import DashboardService
from easy_ecom.domain.services.client_service import ClientService

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

require_login()
store = CsvStore(settings.data_dir)
svc = DashboardService(
    InventoryTxnRepo(store),
    LedgerRepo(store),
    SalesOrdersRepo(store),
    InvoicesRepo(store),
    SalesOrderItemsRepo(store),
    ProductsRepo(store),
    ProductVariantsRepo(store),
    ClientsRepo(store),
    PaymentsRepo(store),
)

user = st.session_state["user"]
roles = user["roles"].split(",")
client_id = user["client_id"]
all_clients = ClientsRepo(store).all()
client_svc = ClientService(ClientsRepo(store))

st.title("Dashboard")
if st.button("Refresh"):
    st.rerun()
auto_refresh = st.toggle("Auto refresh", value=False)
interval = st.selectbox(
    "Auto refresh interval (seconds)", [5, 10, 15, 30], index=2, disabled=not auto_refresh
)
if auto_refresh and st_autorefresh is not None:
    st_autorefresh(interval=interval * 1000, key="dashboard_auto_refresh")
elif auto_refresh:
    st.info("Install streamlit-autorefresh for timed reruns.")

st.session_state["dashboard_last_refreshed_at"] = pd.Timestamp.utcnow().tz_localize(None)
st.caption(
    f"Last refreshed at {st.session_state['dashboard_last_refreshed_at']:%Y-%m-%d %H:%M:%S} UTC"
)

if "SUPER_ADMIN" in roles:
    st.subheader("Scope")
    view_mode = st.radio("Dashboard view", ["Global view", "Specific client view"], horizontal=True)
    scoped_client = None
    if view_mode == "Specific client view":
        client_options = (
            all_clients[["client_id", "business_name"]].copy()
            if not all_clients.empty
            else pd.DataFrame(columns=["client_id", "business_name"])
        )
        choices = [""] + [
            f"{r.client_id} - {r.business_name}" for r in client_options.itertuples(index=False)
        ]
        pick = st.selectbox("Select client", choices)
        if pick:
            scoped_client = pick.split(" - ")[0]
    current_scope_client = scoped_client
else:
    current_scope_client = client_id

warnings = svc.integrity_warnings(current_scope_client)
if warnings:
    st.warning("Data integrity warnings:\n- " + "\n- ".join(warnings))
    for w in warnings:
        log_event(
            AuditRepo(store),
            user.get("user_id", ""),
            current_scope_client or "",
            "dashboard_warning",
            "metrics",
            current_scope_client or "global",
            {"warning": w},
        )

if "SUPER_ADMIN" in roles:
    issues = svc.integrity_issues(current_scope_client)
    if issues:
        st.subheader("Data Issues (admin review)")
        st.dataframe(issues, use_container_width=True)

scorecard = svc.reconciliation_health_scorecard(current_scope_client)
if scorecard:
    st.subheader("Reconciliation Health Scorecard")
    st.dataframe([scorecard], use_container_width=True)

kpis = svc.kpis(current_scope_client)
currency_code, currency_symbol = client_svc.get_currency(current_scope_client or client_id)
cols = st.columns(4)
money_kpis = {
    "Current Stock Value",
    "Revenue MTD",
    "COGS MTD",
    "Gross Profit MTD",
    "Expenses MTD",
    "Net Operating Profit MTD",
    "AOV MTD",
    "Outstanding Invoices",
}
for idx, (name, value) in enumerate(kpis.items()):
    metric_value = (
        format_money(value, currency_code, currency_symbol)
        if name in money_kpis
        else f"{value:,.2f}"
    )
    cols[idx % 4].metric(name, metric_value)

st.divider()
left_filter, right_filter = st.columns(2)
with left_filter:
    freq_label = st.selectbox("Trend granularity", ["Daily", "Weekly", "Monthly"], index=0)
    freq_map = {"Daily": "D", "Weekly": "W", "Monthly": "M"}
with right_filter:
    end_default = pd.Timestamp.utcnow().tz_localize(None).date()
    start_default = end_default - pd.Timedelta(days=30)
    date_range = st.date_input("Date filter", value=(start_default, end_default))

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date = pd.Timestamp(date_range[0])
    end_date = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
else:
    start_date = pd.Timestamp(start_default)
    end_date = pd.Timestamp(end_default) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

freq = freq_map[freq_label]

revenue_trend = svc.revenue_trend(current_scope_client, freq, start_date, end_date)
fig_revenue = px.line(revenue_trend, x="period", y="revenue", markers=True, title="Revenue Trend")
st.plotly_chart(fig_revenue, use_container_width=True)

stock_value = svc.stock_value_by_product(current_scope_client)
fig_stock = px.bar(
    stock_value,
    x="product_name",
    y="stock_value",
    title="Stock Value by Parent Product",
    text_auto=".2s",
)
fig_stock.update_layout(xaxis_title="Product", yaxis_title="Stock Value")
st.plotly_chart(fig_stock, use_container_width=True)

aging = svc.product_aging(current_scope_client)
fig_aging = go.Figure()
fig_aging.add_trace(
    go.Bar(
        name="Sold %",
        x=aging["product_name"],
        y=aging["sold_pct"],
        customdata=aging[["sold_qty", "current_qty", "total_in_qty"]],
        hovertemplate="%{x}<br>Sold %: %{y:.2f}<br>Sold Qty: %{customdata[0]:.2f}<br>Remaining Qty: %{customdata[1]:.2f}<br>Total In: %{customdata[2]:.2f}<extra></extra>",
    )
)
fig_aging.add_trace(
    go.Bar(
        name="Remaining %",
        x=aging["product_name"],
        y=aging["remaining_pct"],
        customdata=aging[["sold_qty", "current_qty", "total_in_qty"]],
        hovertemplate="%{x}<br>Remaining %: %{y:.2f}<br>Sold Qty: %{customdata[0]:.2f}<br>Remaining Qty: %{customdata[1]:.2f}<br>Total In: %{customdata[2]:.2f}<extra></extra>",
    )
)
fig_aging.update_layout(
    title="Product Aging: Sold vs Remaining",
    barmode="group",
    yaxis_title="Percent",
    legend_title="Aging Metrics",
)
st.dataframe(
    aging[["product_name", "sold_qty", "current_qty", "total_in_qty", "sold_pct", "remaining_pct"]],
    use_container_width=True,
)
st.plotly_chart(fig_aging, use_container_width=True)

margin_speed = svc.margin_sell_speed(current_scope_client)
fig_margin = px.scatter(
    margin_speed,
    x="margin_pct",
    y="sell_speed_units_per_day",
    size="revenue_last_30d",
    hover_name="product_name",
    hover_data={
        "revenue_last_30d": ":.2f",
        "cogs_last_30d": ":.2f",
        "margin_pct": ":.2f",
        "units_sold_last_30d": ":.2f",
        "sell_speed_units_per_day": ":.2f",
    },
    title="Gross Margin % vs Sell Speed (Parent Product)",
)
if not margin_speed.empty:
    fig_margin.add_vline(
        x=float(margin_speed["margin_pct"].median()), line_dash="dash", line_color="gray"
    )
    fig_margin.add_hline(
        y=float(margin_speed["sell_speed_units_per_day"].median()),
        line_dash="dash",
        line_color="gray",
    )
fig_margin.update_layout(
    xaxis_title="Margin % (higher is better)",
    yaxis_title="Sell Speed (units/day)",
    legend_title="Revenue Bubble Size",
)
fig_margin.add_annotation(
    xref="paper",
    yref="paper",
    x=0.15,
    y=0.95,
    text="High Margin + Slow Moving (Market More)",
    showarrow=False,
)
fig_margin.add_annotation(
    xref="paper",
    yref="paper",
    x=0.85,
    y=0.95,
    text="High Margin + Fast Moving (Stars)",
    showarrow=False,
)
fig_margin.add_annotation(
    xref="paper",
    yref="paper",
    x=0.15,
    y=0.1,
    text="Low Margin + Slow Moving (Clear/Drop)",
    showarrow=False,
)
fig_margin.add_annotation(
    xref="paper",
    yref="paper",
    x=0.85,
    y=0.1,
    text="Low Margin + Fast Moving (Reprice/Reduce Cost)",
    showarrow=False,
)

st.plotly_chart(fig_margin, use_container_width=True)
with st.expander("How to read this chart"):
    st.write(
        "Right side means better margin. Upper area means faster movement. Bigger bubbles mean more revenue in last 30 days."
    )

income_expense = svc.income_expense_trend(current_scope_client, freq, start_date, end_date)
fig_ie = go.Figure()
fig_ie.add_trace(
    go.Scatter(
        x=income_expense["period"], y=income_expense["income"], mode="lines+markers", name="Income"
    )
)
fig_ie.add_trace(
    go.Scatter(
        x=income_expense["period"],
        y=income_expense["expense"],
        mode="lines+markers",
        name="Expense",
    )
)
fig_ie.update_layout(title="Income vs Expense Trend", xaxis_title="Period", yaxis_title="Amount")
st.plotly_chart(fig_ie, use_container_width=True)

if not income_expense.empty:
    fig_net_profit = px.line(
        income_expense,
        x="period",
        y="profit",
        markers=True,
        title="Net Operating Profit Trend",
    )
    st.plotly_chart(fig_net_profit, use_container_width=True)

lot_profit = svc.lot_profitability(current_scope_client)
fig_lot = go.Figure()
fig_lot.add_trace(go.Bar(name="Lot Cost", x=lot_profit["lot_id"], y=lot_profit["total_cost"]))
fig_lot.add_trace(
    go.Bar(name="Recovered Revenue", x=lot_profit["lot_id"], y=lot_profit["recovered_revenue"])
)
fig_lot.update_layout(
    title="Lot Profitability Recovery", barmode="group", xaxis_title="Lot", yaxis_title="Amount"
)
st.plotly_chart(fig_lot, use_container_width=True)

if "SUPER_ADMIN" in roles and current_scope_client in (None, ""):
    st.subheader("Super Admin Global Charts")
    rev_client = svc.revenue_by_client()
    fig_rev_client = px.bar(rev_client, x="business_name", y="revenue", title="Revenue by Client")
    st.plotly_chart(fig_rev_client, use_container_width=True)

    inv_client = svc.inventory_value_by_client()
    fig_inv_client = px.bar(
        inv_client, x="business_name", y="stock_value", title="Inventory Value by Client"
    )
    st.plotly_chart(fig_inv_client, use_container_width=True)

    st.markdown("### Client Health Flags")
    st.dataframe(svc.client_health_flags(), use_container_width=True)
