"""Quay 1 Seller Leads — entry page (Overview)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import auth, data, kpi
from lib.filters import render_sidebar
from lib.sheets import source_label
from lib.theme import ACCENT, install_theme

st.set_page_config(
    page_title="Quay 1 — Seller Leads",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)
install_theme()

user = auth.gate()

# ── Header ────────────────────────────────────────────────────────────────
st.title("Seller Leads — Overview")
st.caption(f"Data source: **{source_label()}**  ·  signed in as **{user['name']}**")

leads = data.load_leads()
filters = render_sidebar(leads)
view = filters.apply(leads)

# ── KPI row ───────────────────────────────────────────────────────────────
today = pd.Timestamp.now()
last_30 = view[view["Datestamp"] >= today - pd.Timedelta(days=30)]
last_7 = view[view["Datestamp"] >= today - pd.Timedelta(days=7)]
seller = view[view["IsLead"] == "Seller Lead"]
owner = view[view["IsLead"] == "Owner"]
has_deal = view[view["has_deal"]]
worked = view[view["worked"]]

kpi.kpi_row([
    ("Leads in view", len(view), None),
    ("Last 30 days", len(last_30), None),
    ("Last 7 days", len(last_7), None),
    ("Seller leads", len(seller), kpi.pct(len(seller), len(view))),
    ("Has deal", len(has_deal), kpi.pct(len(has_deal), len(view))),
    ("Worked", len(worked), kpi.pct(len(worked), len(view))),
])

st.divider()

# ── Lead trend (stacked area by source) ───────────────────────────────────
left, right = st.columns([2, 1])

with left:
    st.subheader("Leads over time")
    if view.empty:
        st.info("No leads match the current filters.")
    else:
        trend = (
            view.assign(day=view["Datestamp"].dt.to_period("D").dt.to_timestamp())
            .groupby(["day", "Source"]).size().reset_index(name="leads")
        )
        fig = px.area(
            trend, x="day", y="leads", color="Source",
            labels={"day": "", "leads": "Leads"},
        )
        fig.update_layout(height=380, hovermode="x unified", legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Lead mix")
    if not view.empty:
        mix = view["IsLead"].fillna("Unclassified").value_counts().reset_index()
        mix.columns = ["type", "count"]
        fig = px.pie(mix, names="type", values="count", hole=0.55)
        fig.update_traces(textposition="outside", textinfo="label+percent")
        fig.update_layout(height=380, showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)

# ── Suburb leaderboard + action callout ───────────────────────────────────
left, right = st.columns([2, 1])

with left:
    st.subheader("Top suburbs")
    sub = (
        view["Suburb"].dropna().astype(str).str.strip()
        .loc[lambda s: (s.str.len() > 0) & (s.str.len() < 40)]
        .value_counts().head(15).reset_index()
    )
    sub.columns = ["suburb", "count"]
    if not sub.empty:
        fig = px.bar(sub.iloc[::-1], x="count", y="suburb", orientation="h")
        fig.update_layout(height=420, yaxis_title="", xaxis_title="Leads")
        fig.update_traces(marker_color=ACCENT)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No suburbs in view.")

with right:
    st.subheader("Needs attention")
    backlog = view[~view["has_deal"] & ~view["worked"]]
    st.metric("Unworked, no deal", f"{len(backlog):,}")
    st.caption(
        "These are leads with no DealID and no logged call. "
        "Work them in **Action Tracker**."
    )
    st.page_link("pages/3_✅_Action_Tracker.py", label="→ Open Action Tracker", icon="✅")
    st.divider()
    st.caption("Quality by source (highest first)")
    if "Source" in view.columns:
        quality = (
            view.assign(qualified=view["IsLead"].isin(["Seller Lead", "Owner", "Buyer Lead", "Rental Lead"]))
            .groupby("Source").agg(total=("Source", "size"), qualified=("qualified", "sum"))
            .assign(pct=lambda d: (d["qualified"] / d["total"] * 100).round(1))
            .sort_values("pct", ascending=False)
            .head(8)
            .reset_index()
        )
        st.dataframe(
            quality, hide_index=True, use_container_width=True,
            column_config={
                "Source": "Source",
                "total": st.column_config.NumberColumn("Total", format="%d"),
                "qualified": st.column_config.NumberColumn("Qualified", format="%d"),
                "pct": st.column_config.ProgressColumn("Quality", min_value=0, max_value=100, format="%.1f%%"),
            },
        )
