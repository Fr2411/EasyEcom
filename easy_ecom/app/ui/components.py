from __future__ import annotations

import streamlit as st


def show_app_brand() -> None:
    st.sidebar.markdown("## EasyEcom")


def hide_sidebar_navigation() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stSidebarNav"] {display: none;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def hide_main_page_tab() -> None:
    st.markdown(
        """
        <style>
            [data-testid="stSidebarNav"] ul li:first-child {display: none;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_logged_in_user() -> None:
    user = st.session_state.get("user", {})
    email = user.get("email", "")
    if email:
        st.sidebar.markdown(f"**👤 {email}**")
        st.sidebar.divider()


def require_login() -> bool:
    if "user" not in st.session_state:
        hide_sidebar_navigation()
        show_app_brand()
        st.warning("Please login first")
        st.switch_page("pages/01_Login.py")
        st.stop()
    hide_main_page_tab()
    show_app_brand()
    show_logged_in_user()
    return True


def page_header(title: str) -> None:
    st.title(title)
