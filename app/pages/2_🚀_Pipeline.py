"""Pipeline — conversion funnel + deal stage Sankey + division leaderboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib import auth, data, hubspot
from lib.filters import render_sidebar
from lib.theme import ACCENT, PALETTE, install_theme

st.set_page_config(page_title="Pipeline · Quay 1", page_icon="🚀", layout="wide")
install_theme()
user = auth.gate()

st.title("Pipeline")
st.caption("How leads convert from inbound → actioned → deal → closed.")

leads = data.load_leads()
filters = render_sidebar(leads)
view = filters.apply(leads)

if view.empty:
    st.info("No leads in this date range.")
    st.stop()

# ── Funnel ────────────────────────────────────────────────────────────────
st.subheader("Conversion funnel")

n_leads = len(view)
n_qualified = int((view["IsLead"].isin(["Seller Lead", "Owner", "Buyer Lead", "Rental Lead"])).sum())
n_actioned = int(view["actioned"].sum())
n_deal = int(view["has_deal"].sum())

funnel = go.Figure(go.Funnel(
    y=["Leads received", "Qualified lead-type", "Actioned by team", "Deal created"],
    x=[n_leads, n_qualified, n_actioned, n_deal],
    textinfo="value+percent initial",
    marker={"color": PALETTE[: 4]},
))
funnel.update_layout(height=380, margin=dict(l=8, r=8, t=8, b=8))
st.plotly_chart(funnel, use_container_width=True)

# ── Live HubSpot deal stages ──────────────────────────────────────────────
st.subheader("Where the deals are on HubSpot")

col_a, col_b = st.columns([1, 4])
if hubspot.is_configured():
    if col_a.button("↻ Refresh from HubSpot", use_container_width=True):
        hubspot.clear_cache()
        data.load_leads.clear()
        st.rerun()
    col_b.caption(
        "Live stages pulled from HubSpot, cached 30 min. "
        "Click refresh to force a fresh fetch."
    )
else:
    col_b.warning(
        "HubSpot token not configured — falling back to the snapshot stage "
        "from the Excel/Sheet. Add `[hubspot] token = \"…\"` to "
        "`.streamlit/secrets.toml` to enable live data."
    )

with_deal = view[view["has_deal"]].copy()
stage_col = "current_stage" if (hubspot.is_configured() and "current_stage" in with_deal.columns) else "deal_stage"
with_deal = with_deal[with_deal[stage_col].notna()]

if with_deal.empty:
    st.info("No deal-stage data in this slice.")
else:
    by_stage = with_deal[stage_col].astype(str).value_counts().reset_index()
    by_stage.columns = ["stage", "count"]
    fig = px.bar(
        by_stage.iloc[::-1], x="count", y="stage", orientation="h",
        labels={"count": "Deals", "stage": ""},
    )
    fig.update_traces(marker_color=ACCENT)
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

    if hubspot.is_configured() and "amount" in with_deal.columns:
        total_value = pd.to_numeric(with_deal["amount"], errors="coerce").sum()
        if total_value:
            st.caption(
                f"**Total open deal value (filtered)**: R{total_value:,.0f}  "
                f"·  median R{pd.to_numeric(with_deal['amount'], errors='coerce').median():,.0f}"
            )

# ── Division leaderboard ──────────────────────────────────────────────────
st.subheader("Division leaderboard")

board = (
    view[view["Division"].notna()]
    .groupby("Division")
    .agg(
        leads=("Division", "size"),
        actioned=("actioned", "sum"),
        deals=("has_deal", "sum"),
    )
    .reset_index()
)
board["actioned_pct"] = (board["actioned"] / board["leads"] * 100).round(1)
board["deal_pct"] = (board["deals"] / board["leads"] * 100).round(1)
board = board.sort_values("leads", ascending=False)

st.dataframe(
    board, hide_index=True, use_container_width=True,
    column_config={
        "Division": "Division",
        "leads": st.column_config.NumberColumn("Leads", format="%d"),
        "actioned": st.column_config.NumberColumn("Actioned", format="%d"),
        "deals": st.column_config.NumberColumn("Deals", format="%d"),
        "actioned_pct": st.column_config.ProgressColumn("Actioned %", min_value=0, max_value=100, format="%.1f%%"),
        "deal_pct": st.column_config.ProgressColumn("Deal %", min_value=0, max_value=100, format="%.1f%%"),
    },
)
