"""Action Tracker — editable list of leads needing follow-up.

The Actioned tickbox writes to an append-only `Actioned` tab in the
source Google Sheet (or a local CSV in dev). The original Leads tab is
never mutated.
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
    "Leads needing follow-up. Tick the **Actioned** column and click "
    "**Save changes** — each tick appends a row to the Actioned log; "
    "the source Leads tab is never edited."
)

leads = data.load_leads()
filters = render_sidebar(leads)
view = filters.apply(leads)

# Default: only leads with no DealID. Toggle to show all.
show_all = st.toggle("Show all leads (incl. ones with a deal)", value=False)
work = view if show_all else view[~view["has_deal"]]
work = work[work["Email"].notna() & (work["Email"].astype(str).str.strip() != "")]

st.markdown(
    f"**{len(work):,}** leads in view · "
    f"**{int(work['actioned'].sum()):,}** already actioned · "
    f"**{int((~work['actioned']).sum()):,}** outstanding"
)

cols_for_editor = [
    "Datestamp", "ClientName", "Email", "PhoneNumber",
    "Suburb", "Division", "Source", "IsLead",
    "action_flag", "deal_id", "current_stage", "actioned", "action_note",
]
present_cols = [c for c in cols_for_editor if c in work.columns]
work = work[present_cols].sort_values("Datestamp", ascending=False).reset_index(drop=True)

edited = st.data_editor(
    work,
    use_container_width=True,
    hide_index=True,
    height=560,
    num_rows="fixed",
    disabled=[c for c in present_cols if c not in ("actioned", "action_note")],
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
        "current_stage": st.column_config.TextColumn("HubSpot stage (live)"),
        "actioned": st.column_config.CheckboxColumn("Actioned"),
        "action_note": st.column_config.TextColumn("Note"),
    },
    key="action_editor",
)

col1, col2 = st.columns([1, 4])
if col1.button("💾 Save changes", type="primary", use_container_width=True):
    # Find rows that were just flipped to True from False
    before = work.set_index("Email")["actioned"].fillna(False)
    after = edited.set_index("Email")["actioned"].fillna(False)
    notes_after = edited.set_index("Email")["action_note"].fillna("")

    newly_actioned = after & (~before)
    note_changed = (notes_after != work.set_index("Email")["action_note"].fillna(""))
    to_log = (newly_actioned | (after & note_changed))

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
        st.success(f"Saved {n_written} actioned record(s) to the log.")
        data.load_leads.clear()
    else:
        st.info("No changes detected.")
    if errors:
        st.error("Some rows failed:\n" + "\n".join(errors))

col2.caption(
    f"Logged-in user **{user['name']}** is recorded as the actioner. "
    "Notes are optional and append to the same log row."
)

# ── Recent activity ──────────────────────────────────────────────────────
st.divider()
st.subheader("Recent actioned activity")
log = actions.load()
if log.empty:
    st.caption("No actioned events yet.")
else:
    log_view = log.copy().sort_values("actioned_at", ascending=False).head(50)
    st.dataframe(log_view, hide_index=True, use_container_width=True)
