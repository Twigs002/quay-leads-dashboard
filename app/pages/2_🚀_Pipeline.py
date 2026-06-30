"""Pipeline — conversion funnel + deal stage Sankey + division leaderboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib import auth, data
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

# ── Deal stage distribution ───────────────────────────────────────────────
st.subheader("Deal stages (where the open deals sit)")

with_deal = view[view["has_deal"] & view["deal_stage"].notna()].copy()
if with_deal.empty:
    st.info("No DealID + stage data in this slice.")
else:
    by_stage = with_deal["deal_stage"].astype(str).value_counts().reset_index()
    by_stage.columns = ["stage", "count"]
    fig = px.bar(
        by_stage.iloc[::-1], x="count", y="stage", orientation="h",
        labels={"count": "Deals", "stage": ""},
    )
    fig.update_traces(marker_color=ACCENT)
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

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
