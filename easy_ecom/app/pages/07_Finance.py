import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_finance
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.domain.services.finance_service import FinanceService

require_login()
roles = st.session_state["user"]["roles"].split(",")
if not can_access_finance(roles):
    st.error("Access denied")
    st.stop()

store = CsvStore(settings.data_dir)
svc = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
user = st.session_state["user"]
client_id = user["client_id"]
user_id = user["user_id"]

st.title("Finance")
with st.form("ledger"):
    entry_type = st.selectbox("Type", ["earning", "expense"])
    category = st.text_input("Category")
    amount = st.number_input("Amount", min_value=0.01)
    note = st.text_input("Note")
    submit = st.form_submit_button("Post")
if submit:
    svc.add_entry(client_id, entry_type, category, float(amount), "manual", "", note, user_id=user_id)
    st.success("Posted")

st.metric("Profit MTD", f"{svc.profit_mtd(client_id):.2f}")
st.dataframe(LedgerRepo(store).all().query("client_id == @client_id"))
