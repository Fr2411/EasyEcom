import streamlit as st

from easy_ecom.app.ui.styles import CSS
from easy_ecom.core.config import settings

st.set_page_config(page_title=settings.app_title, layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
st.warning(
    "Deprecated frontend: Streamlit UI is in maintenance mode. "
    "Use the Next.js frontend in /frontend for active product development.",
    icon="⚠️",
)

if "user" not in st.session_state:
    st.switch_page("pages/01_Login.py")
else:
    st.switch_page("pages/02_Dashboard.py")
