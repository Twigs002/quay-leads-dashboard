"""Action Tracker — note board for leads needing follow-up.

**Worked** (derived) = the lead's HubSpot deal has ≥1 logged call. To
flip a lead to Worked, log the call in HubSpot — this page does not
override the Worked signal.

What this page IS for: persisting **notes** against a lead (e.g.
"no answer, try Tuesday"). Notes live in Supabase (public.lead_actions)
and are joined back onto the leads frame on read.

The source Google Sheet is never edited.
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
    "**Worked** comes from HubSpot — a deal with a logged call is Worked. "
    "Use this page to add **notes** against leads you've followed up on "
    "(useful for leads with no deal yet, or context that doesn't fit a "
    "HubSpot field). Notes save to Supabase; the source sheet is never edited."
)

leads = data.load_leads()
filters = render_sidebar(leads)
view = filters.apply(leads)

# Default: only leads that aren't Worked. Toggle to see everything.
show_all = st.toggle("Show all leads (including ones already worked)", value=False)
work = view if show_all else view[~view["worked"]]
work = work[work["Email"].notna() & (work["Email"].astype(str).str.strip() != "")]

st.markdown(
    f"**{len(work):,}** leads in view · "
    f"**{int(work['worked'].sum()):,}** already worked (per HubSpot) · "
    f"**{int((~work['worked']).sum()):,}** outstanding"
)

cols_for_editor = [
    "Datestamp", "ClientName", "Email", "PhoneNumber",
    "Suburb", "Division", "Source", "IsLead",
    "action_flag", "deal_id", "current_stage", "num_calls",
    "worked", "action_note",
]
present_cols = [c for c in cols_for_editor if c in work.columns]
work = work[present_cols].sort_values("Datestamp", ascending=False).reset_index(drop=True)

edited = st.data_editor(
    work,
    use_container_width=True,
    hide_index=True,
    height=560,
    num_rows="fixed",
    disabled=[c for c in present_cols if c != "action_note"],
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
        "worked": st.column_config.CheckboxColumn("Worked", help="Derived from HubSpot — read-only"),
        "action_note": st.column_config.TextColumn("Note", help="Your follow-up note. Saves to Supabase on Save."),
    },
    key="action_editor",
)

col1, col2 = st.columns([1, 4])
if col1.button("💾 Save notes", type="primary", use_container_width=True):
    notes_after = edited.set_index("Email")["action_note"].fillna("")
    notes_before = work.set_index("Email")["action_note"].fillna("")
    changed = (notes_after != notes_before) & (notes_after.str.strip() != "")

    n_written = 0
    errors: list[str] = []
    for email, write in changed.items():
        if not write:
            continue
        try:
            actions.append(email=str(email), actioned_by=user["username"], note=str(notes_after.get(email, "")))
            n_written += 1
        except Exception as e:
            errors.append(f"{email}: {e}")

    if n_written:
        st.success(f"Saved {n_written} note(s).")
        data.load_leads.clear()
    else:
        st.info("No note changes to save.")
    if errors:
        st.error("Some rows failed:\n" + "\n".join(errors))

col2.caption(
    f"Logged-in user **{user['name']}** is recorded against each note. "
    "Notes are append-only — every save adds a row to the log, so you can "
    "see a chronology of follow-ups."
)

# ── Recent activity ──────────────────────────────────────────────────────
st.divider()
st.subheader("Recent notes")
log = actions.load()
if log.empty:
    st.caption("No notes logged yet.")
else:
    log_view = log.copy().sort_values("actioned_at", ascending=False).head(50)
    st.dataframe(
        log_view,
        hide_index=True,
        use_container_width=True,
        column_config={
            "actioned_at": st.column_config.DatetimeColumn("When", format="YYYY-MM-DD HH:mm"),
            "actioned_by": "By",
            "email": "Email",
            "note": "Note",
            "actioned": None,  # hide — always true, not meaningful for notes-only flow
            "id": None,
        },
    )
