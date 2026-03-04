import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.repos.csv.customers_repo import CustomersRepo
from easy_ecom.domain.models.customer import CustomerCreate
from easy_ecom.domain.services.customer_service import CustomerService

require_login()
roles = st.session_state["user"]["roles"].split(",")
if not can_access_page(roles, "Customers"):
    st.error("Access denied")
    st.stop()

store = CsvStore(settings.data_dir)
svc = CustomerService(CustomersRepo(store))
client_id = st.session_state["user"]["client_id"]
st.title("Customers")
with st.form("add_customer"):
    full_name = st.text_input("Full name")
    phone = st.text_input("Phone")
    email = st.text_input("Email")
    city = st.text_input("City")
    submit = st.form_submit_button("Add")
if submit:
    svc.create(CustomerCreate(client_id=client_id, full_name=full_name, phone=phone, email=email, city=city, country=""))
    st.success("Customer created")

q = st.text_input("Search")
df = CustomersRepo(store).all().query("client_id == @client_id")
if q:
    df = df[df["full_name"].str.contains(q, case=False, na=False)]
st.dataframe(df)
