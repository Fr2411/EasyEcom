import streamlit as st

from easy_ecom.app.ui.components import hide_sidebar_navigation
from easy_ecom.core.config import settings
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.repos.csv.users_repo import RolesRepo, UserRolesRepo, UsersRepo
from easy_ecom.domain.services.user_service import UserService

if "user" in st.session_state:
    st.switch_page("pages/02_Dashboard.py")

hide_sidebar_navigation()
st.title("Login")
store = CsvStore(settings.data_dir)
service = UserService(UsersRepo(store), RolesRepo(store), UserRolesRepo(store))

email = st.text_input("Email")
password = st.text_input("Password", type="password")
if st.button("Login"):
    user = service.login(email, password)
    if user:
        st.session_state["user"] = user
        st.success("Logged in")
        st.switch_page("pages/02_Dashboard.py")
    else:
        st.error("Invalid credentials")
