"""Global sidebar filters. Stored in st.session_state so every page shares them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import streamlit as st

ALL = "(All)"


@dataclass
class Filters:
    date_from: pd.Timestamp
    date_to: pd.Timestamp
    sources: list[str]
    divisions: list[str]
    lead_types: list[str]
    action_needed_only: bool

    def apply(self, df: pd.DataFrame, date_col: str = "Datestamp") -> pd.DataFrame:
        out = df
        if date_col in out.columns:
            out = out[(out[date_col] >= self.date_from) & (out[date_col] <= self.date_to)]
        if "Source" in out.columns and self.sources:
            out = out[out["Source"].isin(self.sources)]
        if "Division" in out.columns and self.divisions:
            out = out[out["Division"].isin(self.divisions)]
        if "IsLead" in out.columns and self.lead_types:
            out = out[out["IsLead"].isin(self.lead_types)]
        if self.action_needed_only and "has_deal" in out.columns:
            out = out[~out["has_deal"]]
        return out


def render_sidebar(leads: pd.DataFrame) -> Filters:
    st.sidebar.header("Filters")

    today = pd.Timestamp.now().normalize()
    min_d = pd.to_datetime(leads["Datestamp"].min()).normalize()
    default_from = max(min_d, today - pd.Timedelta(days=90))
    date_range = st.sidebar.date_input(
        "Date range",
        value=(default_from.date(), today.date()),
        min_value=min_d.date(),
        max_value=today.date(),
    )
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        d_from, d_to = date_range
    else:
        d_from, d_to = default_from.date(), today.date()

    src_opts = sorted(s for s in leads["Source"].dropna().unique().tolist() if isinstance(s, str))
    div_opts = sorted(d for d in leads["Division"].dropna().unique().tolist() if isinstance(d, str))
    type_opts = sorted(t for t in leads["IsLead"].dropna().unique().tolist() if isinstance(t, str))

    sources = st.sidebar.multiselect("Sources", src_opts, default=[])
    divisions = st.sidebar.multiselect("Divisions", div_opts, default=[])
    lead_types = st.sidebar.multiselect("Lead type", type_opts, default=[])
    action_only = st.sidebar.toggle("Show only Retry / Action Needed", value=False)

    return Filters(
        date_from=pd.Timestamp(d_from),
        date_to=pd.Timestamp(d_to) + pd.Timedelta(hours=23, minutes=59, seconds=59),
        sources=sources,
        divisions=divisions,
        lead_types=lead_types,
        action_needed_only=action_only,
    )
