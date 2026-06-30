"""
Build aggregated, PII-free JSON for the leads dashboard from the source
Excel ("Quay 1 Seller Lead Bank 2024.xlsx") OR — once wired — a pull from
the live Google Sheet.

Outputs JSON files into ../public/data/ that the Next.js app reads at
build time (and re-reads after revalidation when the live sheet hook is
added).

No client names, phone numbers, or emails are written. Only counts,
sums, dates, divisions, sources, suburbs.

Usage:
    python3 scripts/build_data.py /path/to/Quay\ 1\ Seller\ Lead\ Bank\ 2024.xlsx
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "public" / "data"


def _parse_date(s):
    return pd.to_datetime(s, errors="coerce", dayfirst=True)


def _drop_bad_dates(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Drop rows with absurd dates (the workbook has a few mm/dd parses)."""
    today = pd.Timestamp.utcnow().tz_localize(None)
    return df[(df[col].notna()) & (df[col] <= today + pd.Timedelta(days=7))]


def build_overview(leads: pd.DataFrame) -> dict:
    total = len(leads)
    by_type = leads["IsLead"].fillna("Unclassified").astype(str)
    by_type = by_type.where(by_type.str.len() <= 40, "Other")  # nuke long context blobs
    seller = int((by_type == "Seller Lead").sum())
    owner = int((by_type == "Owner").sum())
    buyer = int((by_type == "Buyer Lead").sum())
    rental = int((by_type == "Rental Lead").sum())

    last30 = leads[leads["Datestamp"] >= (pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=30))]
    last7 = leads[leads["Datestamp"] >= (pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=7))]

    return {
        "total_leads": total,
        "seller_leads": seller,
        "owner_leads": owner,
        "buyer_leads": buyer,
        "rental_leads": rental,
        "last_30_days": int(len(last30)),
        "last_7_days": int(len(last7)),
        "date_min": leads["Datestamp"].min().date().isoformat() if total else None,
        "date_max": leads["Datestamp"].max().date().isoformat() if total else None,
        "divisions_with_leads": int(leads["Division"].notna().sum()),
        "leads_no_division": int(leads["Division"].isna().sum()),
    }


def build_daily_trend(leads: pd.DataFrame) -> list[dict]:
    """Daily lead counts, optionally split by source."""
    daily = (
        leads.assign(date=leads["Datestamp"].dt.date)
        .groupby(["date", "Source"])
        .size()
        .reset_index(name="count")
    )
    by_day = (
        daily.pivot_table(index="date", columns="Source", values="count", fill_value=0)
        .reset_index()
    )
    by_day["date"] = by_day["date"].astype(str)
    by_day["total"] = by_day.drop(columns="date").sum(axis=1)
    return by_day.to_dict(orient="records")


def build_monthly_trend(leads: pd.DataFrame) -> list[dict]:
    monthly = (
        leads.assign(month=leads["Datestamp"].dt.to_period("M").astype(str))
        .groupby("month")
        .size()
        .reset_index(name="count")
        .sort_values("month")
    )
    return monthly.to_dict(orient="records")


def build_source_breakdown(leads: pd.DataFrame, raw: pd.DataFrame) -> list[dict]:
    """For each source: total leads, real (Seller/Owner/Buyer/Rental), junk (No Lead)."""
    raw_clean = raw.copy()
    raw_clean["LeadType"] = raw_clean["LeadType"].fillna("Unclassified").astype(str)
    raw_clean["LeadType"] = raw_clean["LeadType"].where(raw_clean["LeadType"].str.len() <= 40, "Other")

    by_src = raw_clean.groupby("Source").agg(
        total=("Source", "size"),
        no_lead=("LeadType", lambda s: int((s == "No Lead").sum())),
        seller=("LeadType", lambda s: int((s == "Seller Lead").sum())),
        owner=("LeadType", lambda s: int((s == "Owner").sum())),
    ).reset_index()
    by_src["qualified"] = by_src["total"] - by_src["no_lead"]
    by_src["quality_pct"] = (by_src["qualified"] / by_src["total"] * 100).round(1)
    by_src = by_src.sort_values("total", ascending=False)
    return by_src.to_dict(orient="records")


def build_division_leaderboard(leads: pd.DataFrame) -> list[dict]:
    div = (
        leads[leads["Division"].notna()]
        .groupby("Division")
        .agg(
            leads=("Division", "size"),
            first_lead=("Datestamp", "min"),
            last_lead=("Datestamp", "max"),
        )
        .reset_index()
        .sort_values("leads", ascending=False)
    )
    div["first_lead"] = div["first_lead"].dt.date.astype(str)
    div["last_lead"] = div["last_lead"].dt.date.astype(str)
    return div.to_dict(orient="records")


def build_division_month_heatmap(leads: pd.DataFrame) -> dict:
    """Pivot: division × month, for the last 18 months. Heatmap data."""
    cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.DateOffset(months=18)
    recent = leads[(leads["Datestamp"] >= cutoff) & leads["Division"].notna()]
    grid = (
        recent.assign(month=recent["Datestamp"].dt.to_period("M").astype(str))
        .groupby(["Division", "month"])
        .size()
        .reset_index(name="count")
    )
    top_divs = (
        recent["Division"].value_counts().head(20).index.tolist()
    )
    grid = grid[grid["Division"].isin(top_divs)]
    months = sorted(grid["month"].unique())
    matrix = []
    for d in top_divs:
        row = {"division": d}
        sub = grid[grid["Division"] == d].set_index("month")["count"].to_dict()
        for m in months:
            row[m] = int(sub.get(m, 0))
        matrix.append(row)
    return {"divisions": top_divs, "months": months, "rows": matrix}


def build_suburb_top(leads: pd.DataFrame, n: int = 25) -> list[dict]:
    sub = leads["Suburb"].dropna().astype(str).str.strip()
    sub = sub[(sub.str.len() > 0) & (sub.str.len() < 40)]  # drop the bot's apology blobs
    return [{"suburb": k, "count": int(v)} for k, v in sub.value_counts().head(n).items()]


def build_property_types(leads: pd.DataFrame) -> list[dict]:
    pt = leads["PropertyType"].dropna().astype(str).str.strip().str.lower()
    pt = pt.replace({"house1": "house", "apartment": "apartment / flat"})
    return [{"type": k, "count": int(v)} for k, v in pt.value_counts().head(15).items()]


def build_onhold(onhold: pd.DataFrame) -> dict:
    if "date" not in onhold.columns:
        return {"by_division": [], "by_week": [], "total_released": 0}
    onhold["date_parsed"] = pd.to_datetime(onhold["date"], errors="coerce", utc=True)
    onhold = onhold[onhold["date_parsed"].notna()]
    onhold["date_parsed"] = onhold["date_parsed"].dt.tz_convert(None)

    by_div = (
        onhold.groupby("division")
        .agg(released=("division", "size"), avg_days_stale=("outOfDateCount", "mean"))
        .reset_index()
        .sort_values("released", ascending=False)
    )
    by_div["avg_days_stale"] = by_div["avg_days_stale"].round(0).fillna(0).astype(int)

    weekly = (
        onhold.assign(week=onhold["date_parsed"].dt.to_period("W").astype(str))
        .groupby("week")
        .size()
        .reset_index(name="released")
        .sort_values("week")
    )

    return {
        "total_released": int(len(onhold)),
        "by_division": by_div.to_dict(orient="records"),
        "by_week": weekly.to_dict(orient="records"),
    }


def build_sold_listed(sold: pd.DataFrame) -> list[dict]:
    if "Division" not in sold.columns:
        return []
    by_div = sold.groupby("Division").size().reset_index(name="contacts").sort_values("contacts", ascending=False)
    return by_div.to_dict(orient="records")


def build_hotwarm(hw: pd.DataFrame) -> list[dict]:
    if "Division" not in hw.columns:
        return []
    by_div = hw.groupby("Division").size().reset_index(name="hot_warm").sort_values("hot_warm", ascending=False)
    return by_div.to_dict(orient="records")


def build_meta_summary(meta: pd.DataFrame) -> dict:
    """Pull the scattered ad-spend cells out of the Meta sheet. They're not
    in a tidy structure; the file has them as labelled cells in column H."""
    out = {
        "instagram_facebook_leads_apr2024_to_now": None,
        "warm_hot": None,
        "listed_sold": None,
        "approx_spend_zar": None,
        "cost_per_lead_zar": None,
        "cost_per_qualified_lead_zar": None,
        "leads_jan_to_jul_2025": None,
        "warm_hot_jan_jul_2025": None,
        "listed_sold_jan_jul_2025": None,
    }
    try:
        labels = meta.iloc[:, 7].astype(str).tolist()
        leads_col = meta.iloc[:, 8].tolist()
        wh_col = meta.iloc[:, 9].tolist()
        ls_col = meta.iloc[:, 10].tolist()

        def find(label_contains, col):
            for i, lbl in enumerate(labels):
                if label_contains.lower() in str(lbl).lower():
                    try:
                        return float(col[i])
                    except (TypeError, ValueError):
                        try:
                            return float(col[i + 1])
                        except Exception:
                            return None
            return None

        out["instagram_facebook_leads_apr2024_to_now"] = find("Total", leads_col)
        out["warm_hot"] = find("Warm / Hot", wh_col)
        out["listed_sold"] = find("Listed / Sold", ls_col)
        out["approx_spend_zar"] = find("Approx Spend (R)", leads_col)
        out["cost_per_lead_zar"] = find("Per Lead", leads_col)
        out["cost_per_qualified_lead_zar"] = find("Per Qualified Lead", leads_col)
    except Exception as e:
        out["_error"] = str(e)
    return out


def build_calls(calls: pd.DataFrame) -> dict:
    calls = calls.copy()
    calls["Date"] = pd.to_datetime(calls["Date"], errors="coerce")
    calls = calls[calls["Date"].notna()]
    weekly = (
        calls.assign(week=calls["Date"].dt.to_period("W").astype(str))
        .groupby("week")
        .agg(total=("Number", "size"))
        .reset_index()
        .sort_values("week")
    )
    by_code = calls["Code"].value_counts().to_dict()
    return {
        "total": int(len(calls)),
        "weekly": weekly.to_dict(orient="records"),
        "new_vs_known": {"new": int(by_code.get(1, 0)), "known": int(by_code.get(2, 0))},
        "date_min": calls["Date"].min().date().isoformat(),
        "date_max": calls["Date"].max().date().isoformat(),
    }


def main(xlsx_path: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Reading {xlsx_path}")

    leads = pd.read_excel(xlsx_path, sheet_name="Leads")
    leads["Datestamp"] = _parse_date(leads["Datestamp"])
    leads = _drop_bad_dates(leads, "Datestamp")
    leads["Division"] = leads["Division"].where(leads["Division"] != "UPDATED BELOW")

    raw = pd.read_excel(xlsx_path, sheet_name="RawLeads")
    raw["Datestamp"] = _parse_date(raw["Datestamp"])

    try:
        onhold = pd.read_excel(xlsx_path, sheet_name="OnHold")
    except Exception:
        onhold = pd.DataFrame()
    try:
        sold = pd.read_excel(xlsx_path, sheet_name="SoldListed")
    except Exception:
        sold = pd.DataFrame()
    try:
        hw = pd.read_excel(xlsx_path, sheet_name="HotWarm")
    except Exception:
        hw = pd.DataFrame()
    try:
        meta = pd.read_excel(xlsx_path, sheet_name="Meta")
    except Exception:
        meta = pd.DataFrame()
    try:
        calls = pd.read_excel(xlsx_path, sheet_name="RawInboundCall")
    except Exception:
        calls = pd.DataFrame()

    artifacts = {
        "overview.json": build_overview(leads),
        "daily.json": build_daily_trend(leads),
        "monthly.json": build_monthly_trend(leads),
        "sources.json": build_source_breakdown(leads, raw),
        "divisions.json": build_division_leaderboard(leads),
        "division_heatmap.json": build_division_month_heatmap(leads),
        "suburbs.json": build_suburb_top(leads),
        "property_types.json": build_property_types(leads),
        "onhold.json": build_onhold(onhold),
        "sold_listed.json": build_sold_listed(sold),
        "hot_warm.json": build_hotwarm(hw),
        "meta_ads.json": build_meta_summary(meta),
        "calls.json": build_calls(calls),
    }

    meta_file = {
        "built_at": datetime.utcnow().isoformat() + "Z",
        "source_file": Path(xlsx_path).name,
        "files": list(artifacts.keys()),
    }

    for name, data in artifacts.items():
        target = OUT_DIR / name
        target.write_text(json.dumps(data, indent=2, default=str))
        print(f"  wrote {target.relative_to(REPO_ROOT)} ({target.stat().st_size:,} bytes)")

    (OUT_DIR / "meta.json").write_text(json.dumps(meta_file, indent=2))
    print(f"\nBuilt {len(artifacts) + 1} files → {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 scripts/build_data.py /path/to/workbook.xlsx")
    main(sys.argv[1])
