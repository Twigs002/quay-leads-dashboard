"""HubSpot deal parsing helpers."""

from __future__ import annotations

import re

import pandas as pd

DEAL_ID_RE = re.compile(r"DealID:\s*(\d+)", re.IGNORECASE)


def extract_deal_id(series: pd.Series) -> pd.Series:
    """Return string DealID extracted from HubspotStatus2 (or NaN)."""
    return series.astype(str).str.extract(DEAL_ID_RE, expand=False)


def annotate(leads: pd.DataFrame) -> pd.DataFrame:
    """Add `deal_id`, `has_deal`, `deal_stage`, `action_flag` columns."""
    out = leads.copy()
    src = out.get("HubspotStatus2", pd.Series([None] * len(out)))
    out["deal_id"] = extract_deal_id(src)
    out["has_deal"] = out["deal_id"].notna()
    out["deal_stage"] = out.get("HubspotStatus", pd.Series([None] * len(out))).astype("object")
    out["action_flag"] = out["has_deal"].map({True: "Has Deal", False: "Retry / Action Needed"})
    return out
