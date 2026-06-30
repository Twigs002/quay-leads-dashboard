"""Read-only Google Sheets / Excel data layer.

The Quay 1 Seller Lead Bank Google Sheet is READ-ONLY for this
dashboard — see feedback_seller_lead_bank_readonly. Writes (Action
Tracker) go to Supabase via lib/actions.py.

When `[google_sheet] id` is set, reads come from the sheet. Otherwise
we fall back to the local Excel fixture (dev only).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _sheet_id() -> Optional[str]:
    return (st.secrets.get("google_sheet", {}).get("id") or "").strip() or None


def _local_xlsx_path() -> Path:
    raw = st.secrets.get("app", {}).get("xlsx_path", "data/leads.xlsx")
    p = Path(raw)
    return p if p.is_absolute() else REPO_ROOT / p


def _get_gspread_client():
    """Lazily authorize a gspread client from the service-account secret."""
    import gspread
    from google.oauth2.service_account import Credentials

    sa = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(
        sa,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    return gspread.authorize(creds)


@st.cache_data(ttl=600, show_spinner=False)
def read_tab(tab_name: str) -> pd.DataFrame:
    """Read a single tab. Sheets if configured, else Excel."""
    sid = _sheet_id()
    if sid:
        gc = _get_gspread_client()
        ws = gc.open_by_key(sid).worksheet(tab_name)
        rows = ws.get_all_records()
        return pd.DataFrame(rows)

    xlsx = _local_xlsx_path()
    if not xlsx.exists():
        st.error(
            f"No data source: {xlsx} not found and no Google Sheet ID set.\n\n"
            "Either copy your Excel to that path, or set `google_sheet.id` "
            "in .streamlit/secrets.toml."
        )
        st.stop()
    return pd.read_excel(xlsx, sheet_name=tab_name)


def source_label() -> str:
    return "Google Sheet" if _sheet_id() else "Local Excel"
