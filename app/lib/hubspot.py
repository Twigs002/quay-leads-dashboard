"""Live HubSpot deal enrichment.

Looks up the current stage + amount + close date + owner + last
modified for every DealID parsed out of HubspotStatus2.

Auth: a Private App token (same pattern as quay-hubspot/scripts/
fetch_hubspot.py — `[hubspot] token` in secrets.toml).

Caching: results held in @st.cache_data for 30 min, keyed on the
sorted tuple of deal IDs. A 'Refresh from HubSpot' button on Pipeline
clears the cache.
"""

from __future__ import annotations

import time
from typing import Iterable

import pandas as pd
import requests
import streamlit as st

API_ROOT = "https://api.hubapi.com"
DEAL_PROPS = [
    "dealname",
    "dealstage",
    "amount",
    "closedate",
    "hs_lastmodifieddate",
    "hubspot_owner_id",
    "pipeline",
    "hs_deal_stage_probability",
]
BATCH_SIZE = 100  # HubSpot max per batch read
THROTTLE_S = 0.35  # ~3 req/s, well under HubSpot's 10/s sustained


def _token() -> str | None:
    return (st.secrets.get("hubspot", {}).get("token") or "").strip() or None


def is_configured() -> bool:
    return _token() is not None


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    })
    return s


def _safe_request(sess: requests.Session, method: str, url: str, **kwargs):
    backoff = 1
    for attempt in range(6):
        time.sleep(THROTTLE_S)
        try:
            r = sess.request(method, url, timeout=30, **kwargs)
        except requests.RequestException:
            time.sleep(backoff); backoff = min(60, backoff * 2); continue
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", backoff))
            time.sleep(wait); backoff = min(60, backoff * 2); continue
        if r.status_code >= 500:
            time.sleep(backoff); backoff = min(60, backoff * 2); continue
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise RuntimeError(f"HubSpot {r.status_code}: {detail}")
        return r.json()
    raise RuntimeError(f"HubSpot: too many retries on {url}")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stage_labels() -> dict[str, str]:
    """Map dealstage-id → human-readable label by reading the Deals pipeline.

    Cached for 1h — pipeline definitions rarely change.
    """
    if not is_configured():
        return {}
    sess = _session()
    data = _safe_request(sess, "GET", f"{API_ROOT}/crm/v3/pipelines/deals")
    out: dict[str, str] = {}
    for pipe in data.get("results", []):
        for stage in pipe.get("stages", []):
            sid = stage.get("id")
            label = stage.get("label") or stage.get("displayOrder") or sid
            if sid:
                out[sid] = label
    return out


@st.cache_data(ttl=1800, show_spinner="Refreshing deal stages from HubSpot…")
def fetch_deals(deal_ids_tuple: tuple[str, ...]) -> pd.DataFrame:
    """Batch-read live deal data for every ID. Cached 30min on the (sorted) tuple.

    Returns columns: deal_id, current_stage_id, current_stage, deal_name,
    amount, close_date, hs_last_modified, hubspot_owner_id, pipeline,
    probability.
    """
    if not is_configured() or not deal_ids_tuple:
        return pd.DataFrame(columns=[
            "deal_id", "current_stage_id", "current_stage", "deal_name",
            "amount", "close_date", "hs_last_modified", "hubspot_owner_id",
            "pipeline", "probability",
        ])

    sess = _session()
    rows: list[dict] = []
    for i in range(0, len(deal_ids_tuple), BATCH_SIZE):
        chunk = deal_ids_tuple[i : i + BATCH_SIZE]
        body = {
            "properties": DEAL_PROPS,
            "inputs": [{"id": did} for did in chunk],
        }
        try:
            data = _safe_request(sess, "POST", f"{API_ROOT}/crm/v3/objects/deals/batch/read", json=body)
        except RuntimeError as e:
            # If the whole batch fails (e.g. an invalid ID in it), fall back to
            # per-ID lookups so we don't lose the whole chunk.
            if "404" in str(e) or "400" in str(e):
                for did in chunk:
                    try:
                        rec = _safe_request(
                            sess, "GET",
                            f"{API_ROOT}/crm/v3/objects/deals/{did}",
                            params={"properties": ",".join(DEAL_PROPS)},
                        )
                        rows.append(_flatten(rec))
                    except RuntimeError:
                        continue
                continue
            raise
        for rec in data.get("results", []):
            rows.append(_flatten(rec))

    if not rows:
        return pd.DataFrame(columns=[
            "deal_id", "current_stage_id", "current_stage", "deal_name",
            "amount", "close_date", "hs_last_modified", "hubspot_owner_id",
            "pipeline", "probability",
        ])

    df = pd.DataFrame(rows)
    df["close_date"] = pd.to_datetime(df["close_date"], errors="coerce", utc=True).dt.tz_convert(None)
    df["hs_last_modified"] = pd.to_datetime(df["hs_last_modified"], errors="coerce", utc=True).dt.tz_convert(None)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["probability"] = pd.to_numeric(df["probability"], errors="coerce")

    labels = fetch_stage_labels()
    df["current_stage"] = df["current_stage_id"].map(labels).fillna(df["current_stage_id"])
    return df


@st.cache_data(ttl=1800, show_spinner="Counting logged calls on deals…")
def fetch_call_counts(deal_ids_tuple: tuple[str, ...]) -> dict[str, int]:
    """Return {deal_id: number_of_logged_calls} via the v4 associations API.

    A deal is considered 'worked' if its call count is > 0.
    """
    if not is_configured() or not deal_ids_tuple:
        return {}

    sess = _session()
    out: dict[str, int] = {}
    for i in range(0, len(deal_ids_tuple), BATCH_SIZE):
        chunk = deal_ids_tuple[i : i + BATCH_SIZE]
        body = {"inputs": [{"id": did} for did in chunk]}
        try:
            data = _safe_request(
                sess, "POST",
                f"{API_ROOT}/crm/v4/associations/deals/calls/batch/read",
                json=body,
            )
        except RuntimeError:
            continue
        for rec in data.get("results", []):
            did = (rec.get("from") or {}).get("id")
            if did:
                out[str(did)] = len(rec.get("to") or [])
        # IDs with no associations don't appear in results — they're 0
        for did in chunk:
            out.setdefault(str(did), 0)
    return out


def _flatten(rec: dict) -> dict:
    props = rec.get("properties") or {}
    return {
        "deal_id": rec.get("id"),
        "current_stage_id": props.get("dealstage"),
        "current_stage": props.get("dealstage"),  # filled with label later
        "deal_name": props.get("dealname"),
        "amount": props.get("amount"),
        "close_date": props.get("closedate"),
        "hs_last_modified": props.get("hs_lastmodifieddate"),
        "hubspot_owner_id": props.get("hubspot_owner_id"),
        "pipeline": props.get("pipeline"),
        "probability": props.get("hs_deal_stage_probability"),
    }


def enrich_leads(leads: pd.DataFrame) -> pd.DataFrame:
    """LEFT JOIN live HubSpot deal data onto leads via deal_id.

    Returns the leads df with extra columns (or unchanged if no token /
    no deal IDs).
    """
    if "deal_id" not in leads.columns or not is_configured():
        for c in ("current_stage", "deal_name", "amount", "close_date", "hs_last_modified", "hubspot_owner_id"):
            if c not in leads.columns:
                leads[c] = pd.NA
        return leads

    ids = (
        leads["deal_id"].dropna().astype(str).str.strip()
        .loc[lambda s: s.str.len() > 0]
        .unique()
    )
    if not len(ids):
        for c in ("current_stage", "deal_name", "amount", "close_date", "hs_last_modified", "hubspot_owner_id"):
            if c not in leads.columns:
                leads[c] = pd.NA
        return leads

    live = fetch_deals(tuple(sorted(ids)))
    if live.empty:
        for c in ("current_stage", "deal_name", "amount", "close_date", "hs_last_modified", "hubspot_owner_id"):
            if c not in leads.columns:
                leads[c] = pd.NA
        return leads

    out = leads.merge(
        live[["deal_id", "current_stage", "deal_name", "amount", "close_date", "hs_last_modified", "hubspot_owner_id"]],
        on="deal_id", how="left",
    )
    # Logged-call count per deal → drives the "worked" semantic
    call_counts = fetch_call_counts(tuple(sorted(ids)))
    out["num_calls"] = out["deal_id"].map(call_counts).fillna(0).astype(int)
    return out


def clear_cache() -> None:
    fetch_deals.clear()
    fetch_stage_labels.clear()
    fetch_call_counts.clear()
