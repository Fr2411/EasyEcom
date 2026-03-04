import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, SalesOrdersRepo
from easy_ecom.domain.services.dashboard_service import DashboardService

require_login()
store = CsvStore(settings.data_dir)
svc = DashboardService(InventoryTxnRepo(store), LedgerRepo(store), SalesOrdersRepo(store), InvoicesRepo(store))
client_id = st.session_state["user"]["client_id"]
k = svc.kpis(client_id)
cols = st.columns(4)
for idx, (name, value) in enumerate(k.items()):
    cols[idx % 4].metric(name, f"{value:.2f}")
