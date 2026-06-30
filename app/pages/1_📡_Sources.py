"""Sources — channel mix, quality, trend."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib import auth, data
from lib.filters import render_sidebar
from lib.theme import ACCENT, install_theme

st.set_page_config(page_title="Sources · Quay 1", page_icon="📡", layout="wide")
install_theme()
user = auth.gate()

st.title("Sources")
st.caption("Where leads come from, how clean each channel is, and how the mix is trending.")

leads = data.load_leads()
raw = data.load_raw()
filters = render_sidebar(leads)
leads_v = filters.apply(leads)
raw_v = filters.apply(raw)

# ── Quality table ────────────────────────────────────────────────────────
st.subheader("Channel quality")

q = (
    raw_v.assign(
        is_junk=raw_v["LeadType"] == "No Lead",
        is_seller=raw_v["LeadType"] == "Seller Lead",
        is_owner=raw_v["LeadType"] == "Owner",
    )
    .groupby("Source")
    .agg(
        total=("Source", "size"),
        junk=("is_junk", "sum"),
        seller=("is_seller", "sum"),
        owner=("is_owner", "sum"),
    )
    .reset_index()
)
q["qualified"] = q["total"] - q["junk"]
q["quality_pct"] = (q["qualified"] / q["total"] * 100).round(1)
q = q.sort_values("total", ascending=False)

st.dataframe(
    q, hide_index=True, use_container_width=True,
    column_config={
        "Source": "Source",
        "total": st.column_config.NumberColumn("Total", format="%d"),
        "junk": st.column_config.NumberColumn("No Lead", format="%d"),
        "seller": st.column_config.NumberColumn("Seller", format="%d"),
        "owner": st.column_config.NumberColumn("Owner", format="%d"),
        "qualified": st.column_config.NumberColumn("Qualified", format="%d"),
        "quality_pct": st.column_config.ProgressColumn(
            "Quality %", min_value=0, max_value=100, format="%.1f%%",
        ),
    },
)

# ── Mix over time ────────────────────────────────────────────────────────
st.subheader("Source mix over time")
if leads_v.empty:
    st.info("No leads in this date range.")
else:
    monthly = (
        leads_v.assign(month=leads_v["Datestamp"].dt.to_period("M").dt.to_timestamp())
        .groupby(["month", "Source"]).size().reset_index(name="leads")
    )
    fig = px.bar(monthly, x="month", y="leads", color="Source", barmode="stack")
    fig.update_layout(height=420, xaxis_title="", legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

# ── Trend per source (small multiples) ──────────────────────────────────
st.subheader("Per-source weekly trend")
if not leads_v.empty:
    top_srcs = leads_v["Source"].value_counts().head(6).index.tolist()
    weekly = (
        leads_v[leads_v["Source"].isin(top_srcs)]
        .assign(week=leads_v["Datestamp"].dt.to_period("W").dt.to_timestamp())
        .groupby(["week", "Source"]).size().reset_index(name="leads")
    )
    fig = px.line(
        weekly, x="week", y="leads", color="Source",
        facet_col="Source", facet_col_wrap=3, facet_col_spacing=0.06,
    )
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    fig.update_xaxes(matches=None, showticklabels=True, title="")
    fig.update_yaxes(matches=None, title="")
    fig.update_layout(height=520, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
