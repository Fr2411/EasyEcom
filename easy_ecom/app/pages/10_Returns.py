import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.sales_repo import RefundsRepo, ReturnItemsRepo, ReturnsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.domain.models.sales import ReturnItem, ReturnRequestCreate
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.returns_service import ReturnsService

require_login()
store = CsvStore(settings.data_dir)
seq = SequenceService(SequencesRepo(store))
inv = InventoryService(InventoryTxnRepo(store), seq)
returns_svc = ReturnsService(
    ReturnsRepo(store),
    ReturnItemsRepo(store),
    RefundsRepo(store),
    FinanceService(LedgerRepo(store), InventoryTxnRepo(store)),
    inv,
)
user = st.session_state["user"]
roles = user["roles"].split(",")
if not can_access_page(roles, "Returns"):
    st.error("Access denied")
    st.stop()
client_id = user["client_id"]

st.title("Returns")
with st.form("create_return"):
    invoice_id = st.text_input("Invoice ID")
    order_id = st.text_input("Order ID")
    customer_id = st.text_input("Customer ID")
    product_id = st.text_input("Product")
    qty = st.number_input("Qty", min_value=0.01)
    unit_selling_price = st.number_input("Unit selling price", min_value=0.01)
    reason = st.text_input("Reason")
    note = st.text_area("Note")
    restock = st.checkbox("Restock inventory on approval")
    submit = st.form_submit_button("Create return request")
if submit:
    try:
        rid = returns_svc.create_request(ReturnRequestCreate(client_id=client_id, invoice_id=invoice_id, order_id=order_id, customer_id=customer_id, requested_by_user_id=user["user_id"], reason=reason, note=note, restock=restock, items=[ReturnItem(product_id=product_id, qty=float(qty), unit_selling_price=float(unit_selling_price))]))
        st.success(f"Return request created: {rid}")
    except Exception as exc:
        st.error(str(exc))

returns_df = ReturnsRepo(store).all()
client_returns = returns_df[returns_df["client_id"] == client_id] if not returns_df.empty else returns_df
st.dataframe(client_returns, use_container_width=True)

if not client_returns.empty:
    pending_ids = client_returns[client_returns["status"] == "PENDING"]["return_id"].tolist()
    if pending_ids:
        return_pick = st.selectbox("Pending return", pending_ids)
        approve_col, reject_col = st.columns(2)
        with approve_col:
            if st.button("Approve"):
                try:
                    returns_svc.approve_request(client_id, return_pick, user["user_id"], roles, True)
                    st.success("Return approved")
                except Exception as exc:
                    st.error(str(exc))
        with reject_col:
            if st.button("Reject"):
                try:
                    returns_svc.approve_request(client_id, return_pick, user["user_id"], roles, False)
                    st.warning("Return rejected")
                except Exception as exc:
                    st.error(str(exc))
