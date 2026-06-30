"""Typed data loaders with caching. Hides whether we're reading the
Excel fixture or the live Google Sheet."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

import pandas as pd
import streamlit as st

from . import actions, deals, hubspot, sheets


def _tab(name_key: str, default: str) -> str:
    return st.secrets.get("google_sheet", {}).get(name_key, default)


@st.cache_data(ttl=600, show_spinner="Loading leads…")
def load_leads() -> pd.DataFrame:
    df = sheets.read_tab(_tab("tab_leads", "Leads"))
    df["Datestamp"] = pd.to_datetime(df.get("Datestamp"), errors="coerce", dayfirst=True)
    df = df[df["Datestamp"].notna()]
    today = pd.Timestamp.now()
    df = df[df["Datestamp"] <= today + pd.Timedelta(days=7)]  # nuke parse blowouts
    if "Division" in df.columns:
        df["Division"] = df["Division"].replace("UPDATED BELOW", pd.NA)
    if "IsLead" in df.columns:
        df["IsLead"] = df["IsLead"].where(df["IsLead"].astype(str).str.len() <= 40, "Other")
    df = deals.annotate(df)
    df = _merge_actioned(df)
    df = hubspot.enrich_leads(df)
    df = _compute_worked(df)
    return df.reset_index(drop=True)


def _compute_worked(leads: pd.DataFrame) -> pd.DataFrame:
    """A lead is 'worked' iff its HubSpot deal has ≥1 logged call.

    Manual marks in the Action Tracker do NOT count — Worked is purely
    a HubSpot signal so the dashboard always reflects what's recorded
    in the CRM.
    """
    out = leads.copy()
    has_call = out.get("num_calls", pd.Series(0, index=out.index)).fillna(0) > 0
    out["worked"] = has_call.astype(bool)
    return out


@st.cache_data(ttl=600, show_spinner="Loading raw leads…")
def load_raw() -> pd.DataFrame:
    df = sheets.read_tab(_tab("tab_raw", "RawLeads"))
    df["Datestamp"] = pd.to_datetime(df.get("Datestamp"), errors="coerce", dayfirst=True)
    df = df[df["Datestamp"].notna()]
    if "LeadType" in df.columns:
        df["LeadType"] = df["LeadType"].where(df["LeadType"].astype(str).str.len() <= 40, "Other")
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_onhold() -> pd.DataFrame:
    df = sheets.read_tab(_tab("tab_onhold", "OnHold"))
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.tz_convert(None)
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_calls() -> pd.DataFrame:
    df = sheets.read_tab(_tab("tab_inbound_calls", "RawInboundCall"))
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_sold_listed() -> pd.DataFrame:
    return sheets.read_tab(_tab("tab_sold_listed", "SoldListed"))


@st.cache_data(ttl=600, show_spinner=False)
def load_hot_warm() -> pd.DataFrame:
    return sheets.read_tab(_tab("tab_hot_warm", "HotWarm"))


@st.cache_data(ttl=600, show_spinner=False)
def load_meta_ads() -> pd.DataFrame:
    return sheets.read_tab(_tab("tab_meta_ads", "Meta"))


def _merge_actioned(leads: pd.DataFrame) -> pd.DataFrame:
    """LEFT JOIN the Supabase lead_actions log onto leads via email."""
    if "Email" not in leads.columns:
        leads["actioned"] = False
        leads["actioned_at"] = pd.NaT
        leads["actioned_by"] = None
        leads["action_note"] = None
        return leads
    log = actions.latest_per_email()
    if log.empty:
        leads["actioned"] = False
        leads["actioned_at"] = pd.NaT
        leads["actioned_by"] = None
        leads["action_note"] = None
        return leads
    out = leads.copy()
    out["email_lc"] = out["Email"].astype(str).str.lower()
    merged = out.merge(
        log[["email_lc", "actioned_at", "actioned_by", "note"]],
        how="left", on="email_lc",
    )
    merged.rename(columns={"note": "action_note"}, inplace=True)
    merged["actioned"] = merged["actioned_at"].notna()
    merged.drop(columns=["email_lc"], inplace=True)
    return merged
