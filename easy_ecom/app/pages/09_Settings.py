import streamlit as st

from easy_ecom.app.ui.components import require_login

require_login()
st.title("Settings")
st.write("Session")
st.json(st.session_state.get("user", {}))
if st.button("Logout"):
    st.session_state.pop("user", None)
    st.success("Logged out")
