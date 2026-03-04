import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, PaymentsRepo, SalesOrderItemsRepo, SalesOrdersRepo, ShipmentsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.domain.models.sales import SaleConfirm, SaleItem
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.sales_service import SalesService

require_login()
roles = st.session_state["user"]["roles"].split(",")
if not can_access_page(roles, "Sales"):
    st.error("Access denied")
    st.stop()

store = CsvStore(settings.data_dir)
seq = SequenceService(SequencesRepo(store))
inv = InventoryService(InventoryTxnRepo(store), seq)
fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
svc = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), inv, seq, fin)
client_id = st.session_state["user"]["client_id"]

st.title("Sales")
customer_id = st.text_input("Customer ID")
product_id = st.text_input("Product ID")
qty = st.number_input("Qty", min_value=0.01)
price = st.number_input("Unit selling price", min_value=0.01)
if st.button("Confirm sale"):
    try:
        payload = SaleConfirm(client_id=client_id, customer_id=customer_id, items=[SaleItem(product_id=product_id, qty=float(qty), unit_selling_price=float(price))])
        result = svc.confirm_sale(payload, {"full_name": "", "phone": "", "address_line1": ""})
        st.success(f"Order confirmed {result['order_id']}")
    except Exception as exc:
        st.error(str(exc))
