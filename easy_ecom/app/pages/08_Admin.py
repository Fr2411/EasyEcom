import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.users_repo import RolesRepo, UserRolesRepo, UsersRepo
from easy_ecom.domain.models.client import ClientCreate
from easy_ecom.domain.models.user import UserCreate
from easy_ecom.domain.services.client_service import ClientService
from easy_ecom.domain.services.user_service import UserService

require_login()
roles = st.session_state["user"]["roles"].split(",")
if "SUPER_ADMIN" not in roles:
    st.error("Access denied")
    st.stop()

store = CsvStore(settings.data_dir)
client_svc = ClientService(ClientsRepo(store))
user_svc = UserService(UsersRepo(store), RolesRepo(store), UserRolesRepo(store))

st.title("Admin")
with st.form("client_create"):
    business_name = st.text_input("Business name")
    owner_name = st.text_input("Owner name")
    email = st.text_input("Email")
    submit_client = st.form_submit_button("Create client")
if submit_client:
    cid = client_svc.create(ClientCreate(business_name=business_name, owner_name=owner_name, email=email, phone="", address=""))
    st.success(f"Client created: {cid}")

with st.form("user_create"):
    client_id = st.text_input("Client ID")
    name = st.text_input("Name")
    email = st.text_input("User email")
    password = st.text_input("Password")
    role = st.selectbox("Role", ["CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_EMPLOYEE", "FINANCE_ONLY", "SUPER_ADMIN"])
    submit_user = st.form_submit_button("Create user")
if submit_user:
    uid = user_svc.create(UserCreate(client_id=client_id, name=name, email=email, password=password, role_code=role))
    st.success(f"User created: {uid}")
