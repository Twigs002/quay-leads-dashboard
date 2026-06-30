"""Unit tests for parsers and merge logic. No Streamlit dependency."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Make `app/lib` importable without spinning up Streamlit
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from lib import deals  # noqa: E402


def test_extract_deal_id_basic():
    s = pd.Series(["DealID: 12345", "no deal", "DealID: 99", None])
    out = deals.extract_deal_id(s)
    assert out.tolist() == ["12345", None, "99", None] or out.fillna("").tolist() == ["12345", "", "99", ""]


def test_extract_deal_id_case_insensitive():
    s = pd.Series(["dealid:    777", "DEALID: 1"])
    out = deals.extract_deal_id(s).fillna("")
    assert out.tolist() == ["777", "1"]


def test_annotate_adds_columns_and_flags():
    df = pd.DataFrame({
        "Email": ["a@x", "b@x", "c@x"],
        "HubspotStatus": ["Qualified", None, "Won"],
        "HubspotStatus2": ["DealID: 42", "missed", "DealID: 999"],
    })
    out = deals.annotate(df)
    for col in ("deal_id", "has_deal", "deal_stage", "action_flag"):
        assert col in out.columns
    assert out["has_deal"].tolist() == [True, False, True]
    assert out.loc[out["has_deal"] == False, "action_flag"].iloc[0] == "Retry / Action Needed"
    assert set(out.loc[out["has_deal"], "action_flag"].unique()) == {"Has Deal"}
