"""Action Tracker — editable list of leads needing follow-up.

A lead is automatically **Worked** once a call is logged on its HubSpot
deal (see lib/data._compute_worked). This page is the **manual
fallback** for leads with no deal yet or where the call wasn't logged
in HubSpot — tick **Mark as worked** to record an override in Supabase.

The source Google Sheet is never edited; writes go to public.lead_actions.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lib import actions, auth, data
from lib.filters import render_sidebar
from lib.theme import install_theme

st.set_page_config(page_title="Action Tracker · Quay 1", page_icon="✅", layout="wide")
install_theme()
user = auth.gate()

st.title("Action Tracker")
st.caption(
    "Auto: any lead whose HubSpot deal has a logged call is marked **Worked**. "
    "Use this page to *manually* mark leads as worked when you've followed up "
    "outside HubSpot. Source sheet is never edited; marks save to Supabase."
)

leads = data.load_leads()
filters = render_sidebar(leads)
view = filters.apply(leads)

# Default: only leads that aren't worked yet. Toggle to show everything.
show_all = st.toggle("Show all leads (including ones already worked)", value=False)
work = view if show_all else view[~view["worked"]]
work = work[work["Email"].notna() & (work["Email"].astype(str).str.strip() != "")]

st.markdown(
    f"**{len(work):,}** leads in view · "
    f"**{int(work['worked'].sum()):,}** already worked · "
    f"**{int((~work['worked']).sum()):,}** outstanding"
)

# Build the editor df — `worked` is read-only (it's derived); only the
# manual-override checkbox and note are editable.
work_view = work.copy()
work_view["mark_as_worked"] = work_view["worked_via_mark"].fillna(False).astype(bool)

cols_for_editor = [
    "Datestamp", "ClientName", "Email", "PhoneNumber",
    "Suburb", "Division", "Source", "IsLead",
    "action_flag", "deal_id", "current_stage", "num_calls",
    "worked", "mark_as_worked", "action_note",
]
present_cols = [c for c in cols_for_editor if c in work_view.columns]
work_view = work_view[present_cols].sort_values("Datestamp", ascending=False).reset_index(drop=True)

edited = st.data_editor(
    work_view,
    use_container_width=True,
    hide_index=True,
    height=560,
    num_rows="fixed",
    disabled=[c for c in present_cols if c not in ("mark_as_worked", "action_note")],
    column_config={
        "Datestamp": st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD HH:mm"),
        "ClientName": "Client",
        "Email": "Email (unique ID)",
        "PhoneNumber": "Phone",
        "Suburb": "Suburb",
        "Division": "Division",
        "Source": "Source",
        "IsLead": "Lead type",
        "action_flag": st.column_config.TextColumn("Status"),
        "deal_id": st.column_config.TextColumn("Deal ID"),
        "current_stage": st.column_config.TextColumn("HubSpot stage"),
        "num_calls": st.column_config.NumberColumn("Calls logged", format="%d"),
        "worked": st.column_config.CheckboxColumn("Worked", help="Derived: call logged OR manual mark"),
        "mark_as_worked": st.column_config.CheckboxColumn("Mark as worked", help="Manual override — saves to Supabase"),
        "action_note": st.column_config.TextColumn("Note"),
    },
    key="action_editor",
)

col1, col2 = st.columns([1, 4])
if col1.button("💾 Save manual marks", type="primary", use_container_width=True):
    before = work_view.set_index("Email")["mark_as_worked"].fillna(False)
    after = edited.set_index("Email")["mark_as_worked"].fillna(False)
    notes_after = edited.set_index("Email")["action_note"].fillna("")
    notes_before = work_view.set_index("Email")["action_note"].fillna("")

    newly_marked = after & (~before)
    note_changed = (notes_after != notes_before)
    to_log = (newly_marked | (after & note_changed))

    n_written = 0
    errors: list[str] = []
    for email, write in to_log.items():
        if not write:
            continue
        try:
            actions.append(email=str(email), actioned_by=user["username"], note=str(notes_after.get(email, "")))
            n_written += 1
        except Exception as e:
            errors.append(f"{email}: {e}")

    if n_written:
        st.success(f"Saved {n_written} manual mark(s).")
        data.load_leads.clear()
    else:
        st.info("No new manual marks to save.")
    if errors:
        st.error("Some rows failed:\n" + "\n".join(errors))

col2.caption(
    f"Logged-in user **{user['name']}** is recorded against each mark. "
    "Notes are optional. The HubSpot-call-derived **Worked** column is "
    "read-only — log the call in HubSpot to flip it."
)

# ── Recent activity ──────────────────────────────────────────────────────
st.divider()
st.subheader("Recent manual marks")
log = actions.load()
if log.empty:
    st.caption("No manual marks logged yet.")
else:
    log_view = log.copy().sort_values("actioned_at", ascending=False).head(50)
    st.dataframe(log_view, hide_index=True, use_container_width=True)
