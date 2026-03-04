import streamlit as st
from easy_ecom.core.config import settings
from easy_ecom.app.ui.styles import CSS

st.set_page_config(page_title=settings.app_title, layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
st.title(settings.app_title)
st.write("Use pages in sidebar to navigate.")
