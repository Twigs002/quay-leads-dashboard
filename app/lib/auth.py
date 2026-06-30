"""Login gate.

Auth is delegated to the same Supabase project that backs the quay-clock
PWA — staff log in with their existing clock-in/out username + PIN.

Flow (mirrors quay-clock/quay-data.js → handlers.login):
  1. supabase.auth.sign_in_with_password(email=f"{username}@quay1.local", password=pin)
  2. Look up the `staff` row by auth_user_id
  3. Reject if staff.active is False
  4. Reject if not (staff.is_super OR staff.is_admin) — leads dashboard
     is superuser-only per project requirements
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

EMAIL_DOMAIN = "quay1.local"


@st.cache_resource(show_spinner=False)
def _client():
    """One Supabase client per Streamlit worker process."""
    from supabase import create_client
    cfg = st.secrets.get("supabase", {})
    url = cfg.get("url", "").strip()
    key = cfg.get("anon_key", "").strip()
    if not url or not key:
        st.error(
            "Supabase not configured. Add `[supabase] url + anon_key` to "
            ".streamlit/secrets.toml (values are the same as quay-clock's "
            "quay-config.js)."
        )
        st.stop()
    return create_client(url, key)


def _email_for(username: str) -> str:
    return f"{username.lower().strip()}@{EMAIL_DOMAIN}"


def _load_staff(sb, auth_user_id: str) -> Optional[dict]:
    res = sb.table("staff").select("*").eq("auth_user_id", auth_user_id).maybe_single().execute()
    return getattr(res, "data", None)


def _do_login(username: str, pin: str) -> tuple[bool, str, dict | None]:
    sb = _client()
    try:
        resp = sb.auth.sign_in_with_password({"email": _email_for(username), "password": pin})
    except Exception as e:
        msg = str(e)
        if "invalid" in msg.lower() or "credentials" in msg.lower():
            return False, "Username or PIN not recognised.", None
        return False, f"Login failed: {msg}", None

    user = getattr(resp, "user", None)
    if not user:
        return False, "Login failed.", None

    staff = _load_staff(sb, user.id)
    if not staff:
        sb.auth.sign_out()
        return False, "No staff record for this account.", None
    if staff.get("active") is False:
        sb.auth.sign_out()
        return False, "Account is disabled.", None
    if not (staff.get("is_super") or staff.get("is_admin")):
        sb.auth.sign_out()
        return False, "Superuser access required for the leads dashboard.", None

    return True, "", {
        "username": staff.get("id") or username.lower(),
        "name": staff.get("name") or username,
        "email": staff.get("email") or _email_for(username),
        "role": staff.get("role") or "",
        "team": staff.get("team") or "",
        "division": staff.get("division") or "",
        "is_admin": bool(staff.get("is_admin")),
        "is_super": bool(staff.get("is_super")),
        "supabase_user_id": user.id,
    }


def _render_login_form() -> None:
    st.markdown(
        """
        <div style="max-width:380px;margin:6vh auto 2rem;">
          <h2 style="margin-bottom:0.25rem;">Quay 1 — Seller Leads</h2>
          <div style="color:#8B98B8;font-size:0.9rem;">
            Sign in with your clock-in username + PIN.<br>
            Superuser access only.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="e.g. pagan", autocomplete="username")
        pin = st.text_input("PIN", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        ok, err, user = _do_login(username, pin)
        if ok:
            st.session_state["quay_user"] = user
            st.rerun()
        else:
            st.error(err or "Login failed.")


def gate() -> dict:
    """Return the signed-in user; render login form & st.stop() if not signed in."""
    user = st.session_state.get("quay_user")
    if not user:
        _render_login_form()
        st.stop()

    with st.sidebar:
        label = user["name"] + (" · super" if user["is_super"] else " · admin" if user["is_admin"] else "")
        st.caption(f"Signed in as **{label}**")
        if st.button("Sign out", use_container_width=True, key="signout_btn"):
            try:
                _client().auth.sign_out()
            except Exception:
                pass
            st.session_state.pop("quay_user", None)
            st.rerun()

    return user


def require_admin(user: dict) -> None:
    if not (user.get("is_super") or user.get("is_admin")):
        st.warning("Admin access required.")
        st.stop()
