"""Raw Data — full searchable / filterable / exportable table."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from lib import auth, data
from lib.filters import render_sidebar
from lib.theme import install_theme

st.set_page_config(page_title="Raw Data · Quay 1", page_icon="📋", layout="wide")
install_theme()
user = auth.gate()

st.title("Raw Data")
st.caption(
    "Full row-level access. Sidebar filters apply. Search box below filters by "
    "client name, email, suburb, address, division, or source."
)

leads = data.load_leads()
filters = render_sidebar(leads)
view = filters.apply(leads)

q = st.text_input("Search", placeholder="name, email, suburb, address, division, source…").strip().lower()
if q:
    cols = ["ClientName", "Email", "PhoneNumber", "PropertyAddress", "Suburb", "Division", "Source", "IsLead"]
    present = [c for c in cols if c in view.columns]
    mask = pd.Series(False, index=view.index)
    for c in present:
        mask = mask | view[c].astype(str).str.lower().str.contains(q, na=False)
    view = view[mask]

st.caption(f"{len(view):,} rows")

display_cols = [
    "Datestamp", "Source", "ClientName", "Email", "PhoneNumber",
    "PropertyAddress", "Suburb", "PropertyType", "Division",
    "IsLead", "action_flag", "deal_id", "deal_stage", "actioned", "actioned_at", "actioned_by",
]
present = [c for c in display_cols if c in view.columns]

st.dataframe(
    view[present].sort_values("Datestamp", ascending=False),
    use_container_width=True,
    hide_index=True,
    height=620,
    column_config={
        "Datestamp": st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD HH:mm"),
        "ClientName": "Client",
        "Email": "Email",
        "PhoneNumber": "Phone",
        "PropertyAddress": "Address",
        "Suburb": "Suburb",
        "PropertyType": "Property",
        "Division": "Division",
        "Source": "Source",
        "IsLead": "Lead type",
        "action_flag": "Status",
        "deal_id": "Deal ID",
        "deal_stage": "Stage",
        "actioned": st.column_config.CheckboxColumn("Actioned"),
        "actioned_at": st.column_config.DatetimeColumn("Actioned at", format="YYYY-MM-DD HH:mm"),
        "actioned_by": "Actioned by",
    },
)

# CSV export
buf = io.StringIO()
view[present].to_csv(buf, index=False)
st.download_button(
    "⬇ Download filtered CSV",
    data=buf.getvalue(),
    file_name="quay_leads_export.csv",
    mime="text/csv",
    use_container_width=False,
)
