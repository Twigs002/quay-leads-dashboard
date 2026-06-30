"""Lead Actions log — Supabase-backed.

The Quay 1 Seller Lead Bank Google Sheet is READ-ONLY for this
dashboard (see feedback_seller_lead_bank_readonly memory). Action
Tracker writes go here instead.

Schema: see supabase/migrations/2026-06-30_lead_actions.sql.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

import pandas as pd
import streamlit as st

from . import auth as _auth


def _client():
    return _auth._client()


def append(email: str, actioned_by: str, note: str = "") -> dict:
    """Insert one row into lead_actions. Returns the inserted row."""
    sb = _client()
    payload = {
        "email": email.strip().lower(),
        "actioned": True,
        "note": (note or "").strip(),
        "actioned_by": actioned_by,
        "actioned_at": dt.datetime.utcnow().isoformat() + "Z",
    }
    res = sb.table("lead_actions").insert(payload).execute()
    load.clear()
    return (getattr(res, "data", None) or [{}])[0]


@st.cache_data(ttl=60, show_spinner=False)
def load() -> pd.DataFrame:
    """Read the full log. Cached 60s so the Action Tracker stays snappy."""
    sb = _client()
    try:
        res = sb.table("lead_actions").select("*").order("actioned_at", desc=True).limit(10000).execute()
        data = getattr(res, "data", None) or []
    except Exception as e:
        st.warning(f"Couldn't read lead_actions: {e}. Run the migration in supabase/migrations/.")
        data = []
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=["email", "actioned", "note", "actioned_by", "actioned_at"])
    df["actioned_at"] = pd.to_datetime(df["actioned_at"], errors="coerce", utc=True).dt.tz_convert(None)
    return df


def latest_per_email(log: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Dedupe to most-recent-per-email, lowercase key."""
    if log is None:
        log = load()
    if log.empty:
        return log
    out = log.copy()
    out["email_lc"] = out["email"].astype(str).str.lower()
    out = out.sort_values("actioned_at").drop_duplicates("email_lc", keep="last")
    return out
