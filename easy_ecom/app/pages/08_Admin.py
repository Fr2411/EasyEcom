import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.core.config import settings
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.users_repo import RolesRepo, UserRolesRepo, UsersRepo
from easy_ecom.domain.models.client import ClientCreate, ClientUpdate
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
    currency_code = st.text_input("Currency code (required, e.g. AED)")
    currency_symbol = st.text_input("Currency symbol (optional)")
    submit_client = st.form_submit_button("Create client")
if submit_client:
    try:
        cid = client_svc.create(ClientCreate(business_name=business_name, owner_name=owner_name, email=email, phone="", address="", currency_code=currency_code, currency_symbol=currency_symbol))
        st.success(f"Client created: {cid}")
    except Exception as exc:
        st.error(str(exc))

clients_df = client_svc.list_clients()
st.subheader("Clients")
st.dataframe(clients_df, use_container_width=True)

if not clients_df.empty:
    client_pick = st.selectbox("Select client to edit", [f"{r.client_id} - {r.business_name}" for r in clients_df.itertuples(index=False)])
    edit_client_id = client_pick.split(" - ")[0]
    selected_client = clients_df[clients_df["client_id"] == edit_client_id].iloc[0]
    with st.form("client_edit"):
        c_business_name = st.text_input("Business name", value=selected_client.get("business_name", ""))
        c_owner_name = st.text_input("Owner name", value=selected_client.get("owner_name", ""))
        c_phone = st.text_input("Phone", value=selected_client.get("phone", ""))
        c_email = st.text_input("Email", value=selected_client.get("email", ""))
        c_address = st.text_input("Address", value=selected_client.get("address", ""))
        c_currency_code = st.text_input("Currency code", value=selected_client.get("currency_code", ""))
        c_currency_symbol = st.text_input("Currency symbol", value=selected_client.get("currency_symbol", ""))
        c_status = st.text_input("Status", value=selected_client.get("status", "active"))
        c_notes = st.text_area("Notes", value=selected_client.get("notes", ""))
        save_client = st.form_submit_button("Save client changes")
    if save_client:
        try:
            client_svc.update(edit_client_id, ClientUpdate(business_name=c_business_name, owner_name=c_owner_name, phone=c_phone, email=c_email, address=c_address, currency_code=c_currency_code, currency_symbol=c_currency_symbol, status=c_status, notes=c_notes))
            st.success("Client updated")
        except Exception as exc:
            st.error(str(exc))

st.divider()
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

if not clients_df.empty:
    user_client_pick = st.selectbox("Users list for client", [f"{r.client_id} - {r.business_name}" for r in clients_df.itertuples(index=False)], key="users_client_pick")
    user_client_id = user_client_pick.split(" - ")[0]
    users_df = user_svc.list_users(user_client_id)
    st.subheader("Users")
    st.dataframe(users_df, use_container_width=True)

    if not users_df.empty:
        user_pick = st.selectbox("Select user to edit", [f"{r.user_id} - {r.name}" for r in users_df.itertuples(index=False)])
        edit_user_id = user_pick.split(" - ")[0]
        selected_user = users_df[users_df["user_id"] == edit_user_id].iloc[0]
        with st.form("user_edit"):
            u_name = st.text_input("Name", value=selected_user.get("name", ""))
            u_email = st.text_input("Email", value=selected_user.get("email", ""))
            u_password = st.text_input("Password", value=selected_user.get("password", ""))
            u_active = st.checkbox("Active", value=str(selected_user.get("is_active", "true")).lower() == "true")
            role_choices = ["SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_EMPLOYEE", "FINANCE_ONLY"]
            current_roles = [r for r in str(selected_user.get("roles", "")).split(",") if r]
            u_roles = st.multiselect("Roles", role_choices, default=current_roles)
            save_user = st.form_submit_button("Save user changes")
        if save_user:
            user_svc.update_user(user_client_id, edit_user_id, u_name, u_email, u_password, u_active, u_roles)
            st.success("User updated")
