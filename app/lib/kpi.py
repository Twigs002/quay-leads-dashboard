"""Small helpers for KPI cards."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def kpi_row(metrics: list[tuple[str, str | int | float, str | None]]) -> None:
    """Render a row of equal-width metric cards.

    Each tuple is (label, value, delta-or-None).
    """
    cols = st.columns(len(metrics))
    for col, (label, value, delta) in zip(cols, metrics):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = f"{value:,}" if float(value).is_integer() else f"{value:,.1f}"
        col.metric(label=label, value=value, delta=delta)


def pct(numerator: float, denominator: float) -> str:
    if not denominator:
        return "—"
    return f"{numerator / denominator * 100:.1f}%"
