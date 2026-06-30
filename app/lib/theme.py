"""Visual theme: Plotly template + CSS injection for the whole app."""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

BG = "#0B1220"
PANEL = "#131C2E"
GRID = "#1F2A44"
TEXT = "#E6EDF3"
MUTED = "#8B98B8"
ACCENT = "#5EEAD4"

# Source-aware palette: pleasant in dark mode, distinct hues per channel
PALETTE = [
    "#5EEAD4",  # teal — primary
    "#A78BFA",  # violet
    "#FB7185",  # rose
    "#FACC15",  # amber
    "#60A5FA",  # blue
    "#34D399",  # emerald
    "#F472B6",  # pink
    "#FB923C",  # orange
    "#22D3EE",  # cyan
    "#C084FC",  # lilac
    "#94A3B8",  # slate
]


def _make_plotly_template() -> go.layout.Template:
    return go.layout.Template(
        layout=go.Layout(
            paper_bgcolor=PANEL,
            plot_bgcolor=PANEL,
            font=dict(color=TEXT, family="Inter, ui-sans-serif, system-ui"),
            colorway=PALETTE,
            margin=dict(l=24, r=24, t=48, b=24),
            xaxis=dict(
                gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                tickfont=dict(color=MUTED),
            ),
            yaxis=dict(
                gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                tickfont=dict(color=MUTED),
            ),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED)),
            hoverlabel=dict(bgcolor=BG, font=dict(color=TEXT)),
        )
    )


def install_theme() -> None:
    """Register the Plotly template and inject app-wide CSS. Idempotent."""
    pio.templates["quay_dark"] = _make_plotly_template()
    pio.templates.default = "quay_dark"

    st.markdown(
        f"""
        <style>
            .stApp {{ background: {BG}; }}
            section[data-testid="stSidebar"] {{
                background: {PANEL};
                border-right: 1px solid {GRID};
            }}
            div[data-testid="stMetric"] {{
                background: {PANEL};
                padding: 1rem 1.2rem;
                border-radius: 12px;
                border: 1px solid {GRID};
            }}
            div[data-testid="stMetricLabel"] {{
                color: {MUTED};
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 0.04em;
            }}
            div[data-testid="stMetricValue"] {{
                color: {TEXT};
                font-weight: 600;
            }}
            div[data-testid="stMetricDelta"] {{
                color: {ACCENT};
            }}
            h1, h2, h3 {{ color: {TEXT}; }}
            .quay-pill {{
                display: inline-block;
                padding: 0.15rem 0.6rem;
                border-radius: 999px;
                font-size: 0.75rem;
                font-weight: 500;
                border: 1px solid {GRID};
                color: {MUTED};
                background: {BG};
            }}
            .quay-pill.green {{ color: #34D399; border-color: rgba(52,211,153,0.4); }}
            .quay-pill.amber {{ color: #FACC15; border-color: rgba(250,204,21,0.4); }}
            .quay-pill.red   {{ color: #FB7185; border-color: rgba(251,113,133,0.4); }}
        </style>
        """,
        unsafe_allow_html=True,
    )
