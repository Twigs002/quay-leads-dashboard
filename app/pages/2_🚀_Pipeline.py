"""Pipeline — conversion funnel + deal stage Sankey + division leaderboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib import auth, data, hubspot
from lib.filters import render_sidebar
from lib.theme import ACCENT, PALETTE, install_theme, stage_colors

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
    cmap = stage_colors(by_stage["stage"].tolist())
    fig = px.bar(
        by_stage.iloc[::-1], x="count", y="stage", orientation="h",
        color="stage", color_discrete_map=cmap,
        labels={"count": "Deals", "stage": ""},
    )
    fig.update_layout(height=420, showlegend=False)
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

# ── Per-division stage breakdown ─────────────────────────────────────────
st.subheader("Where each division's leads sit")
st.caption(
    "For every team's leads in this view: how many are in each HubSpot "
    "stage right now, plus a **No deal yet** bucket for leads with no "
    "associated HubSpot deal."
)

bd = view[view["Division"].notna()].copy()
stage_col = "current_stage" if (hubspot.is_configured() and "current_stage" in bd.columns) else "deal_stage"
bd["__stage"] = bd[stage_col].astype("object").where(bd[stage_col].notna(), "No deal yet")
bd["__stage"] = bd["__stage"].astype(str).str.strip().replace({"": "No deal yet", "nan": "No deal yet", "None": "No deal yet"})

div_totals = bd.groupby("Division").size().sort_values(ascending=False)
top_divs = div_totals.head(15).index.tolist()
matrix = (
    bd[bd["Division"].isin(top_divs)]
    .groupby(["Division", "__stage"]).size().reset_index(name="count")
)

# Order stages: real HubSpot stages first (by total volume), "No deal yet" last
stage_totals = (
    matrix[matrix["__stage"] != "No deal yet"]
    .groupby("__stage")["count"].sum()
    .sort_values(ascending=False)
)
stage_order = stage_totals.index.tolist() + ["No deal yet"]
matrix["__stage"] = pd.Categorical(matrix["__stage"], categories=stage_order, ordered=True)
matrix = matrix.sort_values(["Division", "__stage"])

div_order = div_totals.loc[top_divs].sort_values(ascending=True).index.tolist()

cmap_div = stage_colors(stage_order)
fig = px.bar(
    matrix, x="count", y="Division", color="__stage",
    orientation="h", barmode="stack",
    category_orders={"Division": div_order, "__stage": stage_order},
    color_discrete_map=cmap_div,
    labels={"count": "Leads", "__stage": "HubSpot stage"},
)
fig.update_layout(
    height=max(420, 32 * len(top_divs) + 80),
    legend_title_text="HubSpot stage",
    margin=dict(t=20),
)
st.plotly_chart(fig, use_container_width=True)

# ── Drill-down: one division, full stage table ───────────────────────────
sel_div = st.selectbox(
    "Drill into a division",
    options=sorted(div_totals.index.tolist()),
    index=0 if not div_totals.empty else None,
    key="div_drill",
)
if sel_div:
    sub = bd[bd["Division"] == sel_div]
    by_stage = (
        sub.groupby("__stage").agg(
            leads=("__stage", "size"),
            actioned=("actioned", "sum"),
        ).reset_index()
    )
    by_stage["actioned_pct"] = (by_stage["actioned"] / by_stage["leads"] * 100).round(1)

    if hubspot.is_configured() and "amount" in sub.columns:
        amount_by_stage = (
            sub.assign(amount_num=pd.to_numeric(sub["amount"], errors="coerce"))
            .groupby("__stage")["amount_num"].sum().reset_index(name="total_value")
        )
        by_stage = by_stage.merge(amount_by_stage, on="__stage", how="left")
    by_stage = by_stage.rename(columns={"__stage": "stage"})
    by_stage["__sort"] = by_stage["stage"].apply(lambda s: stage_order.index(s) if s in stage_order else 999)
    by_stage = by_stage.sort_values("__sort").drop(columns="__sort")

    total = int(by_stage["leads"].sum())
    deals_only = int(by_stage[by_stage["stage"] != "No deal yet"]["leads"].sum())
    st.markdown(
        f"**{sel_div}** — {total} leads in this view  ·  "
        f"{deals_only} have a HubSpot deal  ·  "
        f"{total - deals_only} have no deal yet"
    )

    col_config = {
        "stage": "HubSpot stage",
        "leads": st.column_config.NumberColumn("Leads", format="%d"),
        "actioned": st.column_config.NumberColumn("Actioned", format="%d"),
        "actioned_pct": st.column_config.ProgressColumn(
            "Actioned %", min_value=0, max_value=100, format="%.1f%%",
        ),
    }
    if "total_value" in by_stage.columns:
        col_config["total_value"] = st.column_config.NumberColumn(
            "Open value (R)", format="R%,.0f",
        )

    st.dataframe(by_stage, hide_index=True, use_container_width=True, column_config=col_config)
