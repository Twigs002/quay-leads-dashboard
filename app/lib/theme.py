"""Visual theme — mirrors quay-dashboard-v2.

Light paper background, white cards, navy ink, Quay brand yellow accent,
sky-blue secondary. Plotly template + CSS injection together.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ── design tokens (copied from quay-dashboard-v2/quay/styles.css) ──
PAPER = "#EEF2F8"
CARD = "#FFFFFF"
INK = "#1A2746"
SLATE = "#4A566D"
MUTED = "#6B7891"
LINE = "#E0E7F1"
YELLOW = "#FDC503"
YELLOW_DEEP = "#B98A02"
SKY = "#98C5ED"
SKY_DEEP = "#2E6FB0"
NAVY_800 = "#1A2746"
GREEN = "#2F8F63"
AMBER = "#B98A02"
RED = "#D20A03"
BLUE = "#3D5BA6"

# Backwards-compat names used elsewhere in the codebase
BG = PAPER
PANEL = CARD
GRID = LINE
TEXT = INK
ACCENT = YELLOW

# Chart palette — distinct hues that all read on a light card
PALETTE = [
    NAVY_800,    # primary
    SKY_DEEP,    # blue
    YELLOW_DEEP, # amber/gold (legible)
    GREEN,
    RED,
    BLUE,
    "#7C3AED",   # violet
    "#0EA5E9",   # cyan
    "#F97316",   # orange
    "#0F766E",   # teal
    "#9CA3AF",   # slate
]


def _make_plotly_template() -> go.layout.Template:
    return go.layout.Template(
        layout=go.Layout(
            paper_bgcolor=CARD,
            plot_bgcolor=CARD,
            font=dict(color=INK, family="Montserrat, system-ui, -apple-system, sans-serif"),
            colorway=PALETTE,
            margin=dict(l=24, r=24, t=48, b=24),
            xaxis=dict(
                gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE,
                tickfont=dict(color=MUTED),
            ),
            yaxis=dict(
                gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE,
                tickfont=dict(color=MUTED),
            ),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=SLATE)),
            hoverlabel=dict(bgcolor=CARD, font=dict(color=INK), bordercolor=LINE),
        )
    )


def install_theme() -> None:
    """Register the Plotly template and inject app-wide CSS. Idempotent."""
    pio.templates["quay_light"] = _make_plotly_template()
    pio.templates.default = "quay_light"

    st.markdown(
        f"""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link
          href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&family=Permanent+Marker&display=swap"
          rel="stylesheet">
        <style>
            html, body, .stApp,
            [class*="st-"], [data-testid] {{
                font-family: 'Montserrat', system-ui, -apple-system, sans-serif !important;
            }}
            .stApp {{ background: {PAPER}; color: {INK}; }}

            /* sidebar */
            section[data-testid="stSidebar"] {{
                background: {CARD};
                border-right: 1px solid {LINE};
            }}
            section[data-testid="stSidebar"] * {{ color: {INK}; }}
            section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: {MUTED}; }}

            /* KPI cards */
            div[data-testid="stMetric"] {{
                background: {CARD};
                padding: 1rem 1.2rem;
                border-radius: 14px;
                border: 1px solid {LINE};
                box-shadow: 0 1px 2px rgba(30,46,89,.06), 0 1px 1px rgba(30,46,89,.04);
            }}
            div[data-testid="stMetricLabel"] {{
                color: {MUTED};
                font-size: 0.82rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            div[data-testid="stMetricValue"] {{
                color: {INK};
                font-weight: 700;
            }}
            div[data-testid="stMetricDelta"] {{ color: {YELLOW_DEEP}; }}

            /* headings */
            h1, h2, h3, h4 {{
                color: {INK};
                font-family: 'Montserrat', system-ui, sans-serif !important;
                letter-spacing: -0.01em;
            }}
            h1 {{ font-weight: 800; }}
            h2 {{ font-weight: 700; }}
            h3 {{ font-weight: 600; }}

            /* primary buttons — brand yellow */
            div[data-testid="stForm"] button[kind="primary"],
            button[kind="primary"] {{
                background: {YELLOW} !important;
                color: {INK} !important;
                border: 1px solid {YELLOW_DEEP} !important;
                font-weight: 700;
            }}
            button[kind="primary"]:hover {{
                background: {YELLOW_DEEP} !important;
                color: #fff !important;
            }}

            /* dataframes / data editor */
            [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{
                border: 1px solid {LINE};
                border-radius: 12px;
                overflow: hidden;
            }}

            /* status pills (we use these inline in tables / page headers) */
            .quay-pill {{
                display: inline-block;
                padding: 0.15rem 0.7rem;
                border-radius: 999px;
                font-size: 0.75rem;
                font-weight: 600;
                background: {CARD};
                border: 1px solid {LINE};
                color: {SLATE};
            }}
            .quay-pill.green {{ color: {GREEN}; background: #E2F1EA; border-color: rgba(47,143,99,0.25); }}
            .quay-pill.amber {{ color: {YELLOW_DEEP}; background: #FBF1D2; border-color: rgba(185,138,2,0.30); }}
            .quay-pill.red   {{ color: {RED}; background: #FBE2DD; border-color: rgba(210,10,3,0.25); }}

            /* tighten Streamlit's default vertical rhythm a touch */
            .block-container {{ padding-top: 2rem; padding-bottom: 3rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
