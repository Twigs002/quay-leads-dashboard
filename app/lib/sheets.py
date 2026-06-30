"""Google Sheets read + Actioned tab append. Service-account auth.

In dev (no `[google_sheet] id`), all reads fall back to the local Excel
and writes are appended to data/actioned_log.csv instead of the sheet.
"""

from __future__ import annotations

import csv
import datetime as dt
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


def _actioned_log_path() -> Path:
    return REPO_ROOT / "data" / "actioned_log.csv"


def _get_gspread_client():
    """Lazily authorize a gspread client from the service-account secret."""
    import gspread
    from google.oauth2.service_account import Credentials

    sa = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(
        sa,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
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


def append_actioned(email: str, actioned_by: str, note: str = "") -> None:
    """Append one row to the Actioned tab (or local CSV fallback)."""
    sid = _sheet_id()
    row = [
        dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        email,
        actioned_by,
        note,
    ]
    if sid:
        tab_name = st.secrets.get("google_sheet", {}).get("tab_actioned", "Actioned")
        gc = _get_gspread_client()
        sh = gc.open_by_key(sid)
        try:
            ws = sh.worksheet(tab_name)
        except Exception:
            ws = sh.add_worksheet(title=tab_name, rows=1000, cols=4)
            ws.append_row(["actioned_at", "email", "actioned_by", "note"])
        ws.append_row(row, value_input_option="USER_ENTERED")
    else:
        path = _actioned_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        with path.open("a", newline="") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["actioned_at", "email", "actioned_by", "note"])
            w.writerow(row)
    read_actioned.clear()


@st.cache_data(ttl=120, show_spinner=False)
def read_actioned() -> pd.DataFrame:
    """Read the Actioned log (sheet tab or local CSV)."""
    sid = _sheet_id()
    if sid:
        tab_name = st.secrets.get("google_sheet", {}).get("tab_actioned", "Actioned")
        try:
            return read_tab(tab_name)
        except Exception:
            return pd.DataFrame(columns=["actioned_at", "email", "actioned_by", "note"])
    p = _actioned_log_path()
    if not p.exists():
        return pd.DataFrame(columns=["actioned_at", "email", "actioned_by", "note"])
    return pd.read_csv(p)


def source_label() -> str:
    return "Google Sheet" if _sheet_id() else "Local Excel"
