from __future__ import annotations

import streamlit as st


def require_login() -> bool:
    if "user" not in st.session_state:
        st.warning("Please login first")
        st.stop()
    return True


def page_header(title: str) -> None:
    st.title(title)
