import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.app.ui.formatters import format_money
from easy_ecom.core.audit import log_event
from easy_ecom.core.config import settings
from easy_ecom.data.repos.csv.audit_repo import AuditRepo
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
from easy_ecom.domain.services.client_service import ClientService
from easy_ecom.domain.services.dashboard_service import DashboardService

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

st.title("Business Health Dashboard")
st.caption("Decision-focused dashboard for profitability, product performance, inventory, receivables, and data trust.")

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

currency_code, currency_symbol = client_svc.get_currency(current_scope_client or client_id)

st.divider()
flt_a, flt_b = st.columns(2)
with flt_a:
    freq_label = st.selectbox("Trend granularity", ["Daily", "Weekly", "Monthly"], index=1)
    freq_map = {"Daily": "D", "Weekly": "W", "Monthly": "M"}
with flt_b:
    end_default = pd.Timestamp.utcnow().tz_localize(None).date()
    start_default = end_default - pd.Timedelta(days=60)
    date_range = st.date_input("Date filter", value=(start_default, end_default))

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date = pd.Timestamp(date_range[0])
    end_date = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
else:
    start_date = pd.Timestamp(start_default)
    end_date = pd.Timestamp(end_default) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

freq = freq_map[freq_label]

# Section 1 — Business Health Snapshot
st.header("1) Business Health Snapshot")
snapshot = svc.business_health_snapshot(current_scope_client)

kpi_meta = [
    ("Revenue", "Confirmed sales totals.", "money"),
    ("Gross Profit", "Revenue - COGS.", "money"),
    ("Net Operating Profit", "Revenue - COGS - Expenses.", "money"),
    ("Gross Margin %", "Gross Profit / Revenue.", "pct"),
    ("Inventory Value", "Current positive stock lots at unit cost.", "money"),
    ("Outstanding Receivables", "Unpaid + partial invoices after payments.", "money"),
    ("Data Health Score", "Starts at 100 and decreases with reconciliation issues.", "pct"),
]
kpi_cols = st.columns(4)
for i, (name, help_txt, fmt) in enumerate(kpi_meta):
    col = kpi_cols[i % 4]
    val = float(snapshot.get(name, 0.0))
    if fmt == "money":
        shown = format_money(val, currency_code, currency_symbol)
    else:
        shown = f"{val:,.1f}%"
    delta_color = "off"
    if name in {"Gross Margin %", "Data Health Score"}:
        delta = "Healthy" if val >= 70 else "Watch"
        col.metric(name, shown, delta=delta, delta_color=delta_color)
    else:
        col.metric(name, shown)
    col.caption(help_txt)

# Section 2 — Trend View
st.header("2) Trend View")
trend = svc.trend_summary(current_scope_client, freq, start_date, end_date)
if trend.empty:
    st.info("No trend data for selected range.")
else:
    trend_fig = go.Figure()
    trend_fig.add_trace(go.Scatter(x=trend["period"], y=trend["revenue"], mode="lines+markers", name="Revenue"))
    trend_fig.add_trace(go.Scatter(x=trend["period"], y=trend["gross_profit"], mode="lines+markers", name="Gross Profit"))
    trend_fig.add_trace(go.Scatter(x=trend["period"], y=trend["net_operating_profit"], mode="lines+markers", name="Net Operating Profit"))
    trend_fig.add_trace(go.Scatter(x=trend["period"], y=trend["expenses"], mode="lines+markers", name="Expenses"))
    trend_fig.update_layout(title="Revenue, Gross Profit, Net Operating Profit, and Expenses", yaxis_title="Amount")
    st.plotly_chart(trend_fig, use_container_width=True)

    inv_fig = px.area(trend, x="period", y="inventory_value", title="Inventory Value Trend")
    inv_fig.update_layout(yaxis_title="Inventory Value")
    st.plotly_chart(inv_fig, use_container_width=True)

# Section 3 — Product Performance
st.header("3) Product Performance")
perf = svc.product_performance(current_scope_client)
left, right = st.columns(2)
with left:
    st.subheader("Top Products by Revenue (last 30 days)")
    st.dataframe(perf["top_revenue"][["product_name", "revenue", "gross_profit", "margin_pct"]], use_container_width=True)
    st.subheader("Lowest-Margin Products (last 30 days)")
    st.dataframe(perf["lowest_margin"][["product_name", "revenue", "gross_profit", "margin_pct"]], use_container_width=True)
with right:
    st.subheader("Top Products by Gross Profit (last 30 days)")
    st.dataframe(perf["top_gross_profit"][["product_name", "gross_profit", "revenue", "margin_pct"]], use_container_width=True)
    st.subheader("Slow-Moving Products (last 30 days)")
    st.dataframe(perf["slow_moving"][["product_name", "sell_speed_units_per_day", "units_sold_last_30d", "stock_value"]], use_container_width=True)

st.subheader("Aging / Dead Stock Candidates")
st.dataframe(perf["aging_dead_stock"][["product_name", "stock_value", "units_sold_last_30d", "sell_speed_units_per_day"]], use_container_width=True)

st.subheader("Gross Margin % vs Sale Speed (Featured)")
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
    title="Gross Margin % vs Sale Speed (Parent Product)",
)
if not margin_speed.empty:
    fig_margin.add_vline(x=float(margin_speed["margin_pct"].median()), line_dash="dash", line_color="gray")
    fig_margin.add_hline(y=float(margin_speed["sell_speed_units_per_day"].median()), line_dash="dash", line_color="gray")
fig_margin.update_layout(
    xaxis_title="Gross Margin % (right is better)",
    yaxis_title="Sale Speed (units/day; up is better)",
)
st.plotly_chart(fig_margin, use_container_width=True)
st.caption(
    "Business meaning: upper-right = strongest products (high margin + high speed). "
    "Lower-left = weakest products (low margin + slow movement)."
)

# Section 4 — Inventory Health
st.header("4) Inventory Health")
inv_health = svc.inventory_health(current_scope_client)
inv_cols = st.columns(4)
inv_cols[0].metric("Current Stock Value", format_money(inv_health["current_stock_value"], currency_code, currency_symbol))
inv_cols[1].metric("Low Stock Products", f"{int(inv_health['low_stock_count'])}")
inv_cols[2].metric("Out of Stock Products", f"{int(inv_health['out_of_stock_count'])}")
inv_cols[3].metric("Top-5 Stock Concentration", f"{float(inv_health['top_5_stock_concentration_pct']):.1f}%")
st.dataframe(inv_health["aging"][["product_name", "sold_pct", "remaining_pct", "sold_qty", "current_qty"]], use_container_width=True)

# Section 5 — Financial / Receivables Health
st.header("5) Financial / Receivables Health")
fin = svc.financial_health(current_scope_client, freq, start_date, end_date)
fin_cols = st.columns(3)
fin_cols[0].metric("Outstanding Invoices", format_money(fin["outstanding_invoices"], currency_code, currency_symbol))
fin_cols[1].metric("Unpaid Confirmed Sales", format_money(fin["unpaid_confirmed_sales"], currency_code, currency_symbol))
fin_cols[2].metric("Expense Pressure", f"{float(fin['expense_pressure_pct']):.1f}% of revenue")

recv = fin["receivables_trend"]
if not recv.empty:
    st.plotly_chart(px.line(recv, x="period", y="outstanding_receivables", markers=True, title="Receivables Trend"), use_container_width=True)

exp = fin["expense_trend"]
if not exp.empty:
    st.plotly_chart(px.bar(exp, x="period", y="expenses", title="Expense Trend"), use_container_width=True)

# Section 6 — Data Trust / Reconciliation
st.header("6) Data Trust / Reconciliation")
scorecard = svc.reconciliation_health_scorecard(current_scope_client)
if scorecard:
    if "SUPER_ADMIN" in roles:
        st.dataframe([scorecard], use_container_width=True)
        issues = svc.integrity_issues(current_scope_client)
        if issues:
            st.warning(f"{len(issues)} reconciliation issues detected. Review details below.")
            st.dataframe(issues, use_container_width=True)
    else:
        warnings = svc.integrity_warnings(current_scope_client)
        if warnings:
            st.warning("Data trust alerts:\n- " + "\n- ".join(warnings[:5]))
        else:
            st.success("Data trust status: Good (no active integrity warnings).")

warnings = svc.integrity_warnings(current_scope_client)
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

if "SUPER_ADMIN" in roles and current_scope_client in (None, ""):
    st.subheader("Super Admin Global Monitoring")
    rev_client = svc.revenue_by_client()
    inv_client = svc.inventory_value_by_client()
    st.plotly_chart(px.bar(rev_client, x="business_name", y="revenue", title="Revenue by Client"), use_container_width=True)
    st.plotly_chart(px.bar(inv_client, x="business_name", y="stock_value", title="Inventory Value by Client"), use_container_width=True)
    st.dataframe(svc.client_health_flags(), use_container_width=True)
