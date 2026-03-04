import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, PaymentsRepo, SalesOrderItemsRepo, SalesOrdersRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.core.audit import log_event
from easy_ecom.data.repos.csv.audit_repo import AuditRepo
from easy_ecom.domain.services.dashboard_service import DashboardService

require_login()
store = CsvStore(settings.data_dir)
svc = DashboardService(
    InventoryTxnRepo(store),
    LedgerRepo(store),
    SalesOrdersRepo(store),
    InvoicesRepo(store),
    SalesOrderItemsRepo(store),
    ProductsRepo(store),
    ClientsRepo(store),
    PaymentsRepo(store),
)

user = st.session_state["user"]
roles = user["roles"].split(",")
client_id = user["client_id"]
all_clients = ClientsRepo(store).all()

st.title("Dashboard")

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
        log_event(AuditRepo(store), user.get("user_id", ""), current_scope_client or "", "dashboard_warning", "metrics", current_scope_client or "global", {"warning": w})

kpis = svc.kpis(current_scope_client)
cols = st.columns(4)
for idx, (name, value) in enumerate(kpis.items()):
    cols[idx % 4].metric(name, f"{value:,.2f}")

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
    stock_value, x="product_name", y="stock_value", title="Stock Value by Product", text_auto=".2s"
)
fig_stock.update_layout(xaxis_title="Product", yaxis_title="Stock Value")
st.plotly_chart(fig_stock, use_container_width=True)

aging = svc.product_aging(current_scope_client)
fig_aging = go.Figure()
fig_aging.add_trace(go.Bar(name="Sold %", x=aging["product_name"], y=aging["sold_pct"]))
fig_aging.add_trace(go.Bar(name="Remaining %", x=aging["product_name"], y=aging["remaining_pct"]))
fig_aging.update_layout(
    title="Product Aging: Sold vs Remaining", barmode="group", yaxis_title="Percent"
)
st.plotly_chart(fig_aging, use_container_width=True)

margin_speed = svc.margin_sell_speed(current_scope_client)
fig_margin = px.scatter(
    margin_speed,
    x="margin_pct",
    y="sell_speed",
    size="revenue",
    hover_name="product_name",
    title="Margin % vs Sell Speed",
)
fig_margin.update_layout(xaxis_title="Margin %", yaxis_title="Sell Speed (units/day)")
st.plotly_chart(fig_margin, use_container_width=True)

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
