"""Login gate. streamlit-authenticator + secrets.toml. Single seam to swap
for the quay-clock Apps Script admin_check later."""

from __future__ import annotations

from typing import Optional

import streamlit as st
import streamlit_authenticator as stauth


def _build_authenticator() -> stauth.Authenticate:
    auth = st.secrets.get("auth", {})
    credentials = auth.get("credentials", {})
    cookie = auth.get("cookie", {})
    if not credentials:
        st.error(
            "No auth credentials configured. Copy .streamlit/secrets.example.toml "
            "to .streamlit/secrets.toml and add at least one user."
        )
        st.stop()
    return stauth.Authenticate(
        credentials={"usernames": dict(credentials.get("usernames", {}))},
        cookie_name=cookie.get("name", "quay_leads_session"),
        cookie_key=cookie.get("key", "change-me"),
        cookie_expiry_days=int(cookie.get("expiry_days", 7)),
    )


def gate() -> dict:
    """Render the login form (if needed) and return the session user dict.

    Returns:
        {"username": str, "name": str, "email": str, "admin": bool}

    Halts the script via st.stop() if not authenticated.
    """
    if "authenticator" not in st.session_state:
        st.session_state.authenticator = _build_authenticator()
    authenticator: stauth.Authenticate = st.session_state.authenticator

    authenticator.login(location="main", key="login", fields={"Form name": "Quay 1 — Seller Leads"})
    status = st.session_state.get("authentication_status")
    if status is False:
        st.error("Wrong PIN. Try again.")
        st.stop()
    if status is None:
        st.info("Enter your username and PIN to continue.")
        st.stop()

    username = st.session_state.get("username", "")
    name = st.session_state.get("name", username)
    creds_users = st.secrets.get("auth", {}).get("credentials", {}).get("usernames", {})
    user_row = dict(creds_users.get(username, {}))
    user = {
        "username": username,
        "name": name,
        "email": user_row.get("email", ""),
        "admin": bool(user_row.get("admin", False)),
    }

    with st.sidebar:
        st.caption(f"Signed in as **{user['name']}**" + (" · admin" if user["admin"] else ""))
        authenticator.logout(button_name="Sign out", location="sidebar", key="logout")

    return user


def require_admin(user: dict) -> None:
    if not user.get("admin"):
        st.warning("Admin access required.")
        st.stop()
