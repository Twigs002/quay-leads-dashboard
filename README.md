# Quay 1 — Seller Leads Dashboard

Interactive dashboard for the Quay 1 Realty seller-lead pipeline. Reads the
**Quay 1 Seller Lead Bank** workbook (Excel locally, Google Sheet in prod),
lets the team triage leads, mark actions, and see channel/division
performance at a glance.

Built for the COO so the same lead picture is shared across leadership.

---

## What's in it

Five tabs, gated behind a PIN login (only superusers get in):

| Tab | What it does |
|---|---|
| **Overview** | KPIs (Leads / 30d / 7d / Seller / Has Deal / Actioned), leads-over-time, lead-mix donut, top suburbs, quality table |
| **Sources** | Channel quality % (Buyers Bot, Meta fb/ig, Email, Google Forms, etc.), source mix over months, per-source weekly trend |
| **Pipeline** | Conversion funnel (Leads → Qualified → Actioned → Deal), deal-stage distribution, division leaderboard |
| **Action Tracker** | Editable table of leads needing follow-up. Tick **Actioned** → appends to an audit log. Email is the unique identifier. |
| **Raw Data** | Full row-level search + filter + CSV export |

Every page shares a sidebar with **date range**, **division**, **source**,
**lead-type**, and a "Retry / Action Needed only" toggle.

**Theme**: dark, neutral-on-deep-navy, teal accent. Plotly charts use a
matched template so every screen looks like one product.

---

## Local development

```bash
git clone https://github.com/Twigs002/quay-leads-dashboard.git
cd quay-leads-dashboard

# Python 3.11+ recommended
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Data: drop your Excel here (gitignored)
mkdir -p data
cp ~/Downloads/Quay\ 1\ Seller\ Lead\ Bank\ 2024.xlsx data/leads.xlsx

# Secrets: copy and edit
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
python3 scripts/hash_pin.py 1234           # generate a bcrypt hash
# Paste the hash into secrets.toml under [auth.credentials.usernames.<name>]

streamlit run app/Home.py
```

Open `http://localhost:8501` and log in with the PIN you hashed.

### Running the unit tests

```bash
pip install pytest
python3 -m pytest tests/ -q
```

---

## Project structure

```
quay-leads-dashboard/
├── app/
│   ├── Home.py                   # entry page (Overview, login form)
│   ├── pages/
│   │   ├── 1_📡_Sources.py        # channel mix, quality, trend
│   │   ├── 2_🚀_Pipeline.py       # funnel, deal stages, division leaderboard
│   │   ├── 3_✅_Action_Tracker.py # editable triage table
│   │   └── 4_📋_Raw_Data.py       # full searchable table + CSV export
│   └── lib/
│       ├── auth.py               # streamlit-authenticator gate
│       ├── data.py               # cached loaders, Actioned-log join
│       ├── deals.py              # DealID regex, action_flag classification
│       ├── filters.py            # sidebar global filters
│       ├── kpi.py                # KPI row helper
│       ├── sheets.py             # gspread r/w + Excel fallback
│       └── theme.py              # dark Plotly template + CSS injection
├── scripts/
│   ├── build_data.py             # one-shot Excel → JSON cache (legacy / optional)
│   └── hash_pin.py               # bcrypt hash a PIN for secrets.toml
├── tests/test_data.py
├── .streamlit/
│   ├── config.toml               # dark theme
│   └── secrets.example.toml      # template
├── requirements.txt
└── README.md
```

---

## Deploy to Streamlit Community Cloud

1. Push the repo to GitHub (this repo: `Twigs002/quay-leads-dashboard`).
2. Sign in at <https://share.streamlit.io> with GitHub.
3. **New app** → pick `Twigs002/quay-leads-dashboard`, branch `main`,
   main file `app/Home.py`.
4. **Advanced settings → Secrets** → paste the entire body of your
   `.streamlit/secrets.toml` (including the `[gcp_service_account]`
   block).
5. **Deploy.** Your URL is `https://<app-name>.streamlit.app` — rename it
   to `quay-leads.streamlit.app` (or similar) in app settings.
6. Every `git push origin main` auto-redeploys.

Private repos are supported on the free tier as long as you've connected
the right GitHub account.

---

## HubSpot — live deal stage

When a `[hubspot] token` is set in secrets, every `DealID` parsed out of
`HubspotStatus2` is enriched with live data from HubSpot:

- `current_stage` — the live stage label (translated from stage IDs via
  `/crm/v3/pipelines/deals`)
- `amount`, `close_date`, `hs_last_modified`, `hubspot_owner_id`,
  `deal_name`

Surfaces:
- **Pipeline → Where the deals are on HubSpot** — live stage bar +
  total/median deal value, with a ↻ **Refresh from HubSpot** button
- **Action Tracker** — extra `HubSpot stage (live)` column
- **Raw Data** — adds `current_stage`, `Deal R`, `Expected close`,
  `Last touched`, sortable + searchable

Implementation notes:
- Batch reads of 100 IDs per call, ~3 req/s (gentle on HubSpot's
  10 req/s limit), 6-attempt back-off on 429 / 5xx
- Results cached 30 min via `@st.cache_data`; pipelines cached 1 h
- Token: paste your Private App token under `[hubspot] token` in
  `.streamlit/secrets.toml` (same one used by `Twigs002/quay-hubspot`'s
  GitHub Actions secret `HUBSPOT_TOKEN`)
- Degrades gracefully: no token = dashboard still works, just shows the
  stale snapshot stage from the workbook

---

## Auto-update from the Google Sheet

Three options, recommended first.

### A. Live pull on every page render (recommended)

Mechanism: `lib/sheets.py` reads from the sheet via a service account,
cached by Streamlit for **10 minutes per loader** (`@st.cache_data(ttl=600)`).

Setup:

1. In Google Cloud Console, create a **service account** + JSON key.
2. Share your Google Sheet with the service account's email
   (`xxx@yyy.iam.gserviceaccount.com`) as **Editor** (so the Action
   Tracker can append to the `Actioned` tab).
3. Paste the JSON contents into `secrets.toml` under
   `[gcp_service_account]`.
4. Set `google_sheet.id` in `secrets.toml` to your sheet's ID (the part
   between `/d/` and `/edit` in the URL).
5. Restart the app.

**Pros**: fresh data automatically, no infra. Quotas (60 reads/min/project)
are fine for a 5-superuser dashboard.
**Cons**: each user's first hit after 10 min pays the read cost.

### B. GitHub Actions cron → JSON cache

Mechanism: `.github/workflows/refresh.yml` runs `scripts/build_data.py`
every 30 min, commits the resulting `public/data/*.json` to the repo,
and the Streamlit app reads from JSON instead of the live sheet.

**Pros**: no service account in Streamlit Cloud secrets; great when
sheet reads are rate-limited.
**Cons**: lag = cron interval; commit clutter; needs separate write
path for the Actioned log (can't be GitHub-Actions-only).

### C. Apps Script push-on-edit webhook

Mechanism: a `onEdit` trigger in the Sheet's Apps Script POSTs to a
webhook that clears Streamlit's cache.

**Pros**: real-time.
**Cons**: Streamlit Community Cloud doesn't expose custom HTTP
endpoints; you'd need a tiny sidecar service. Not worth the complexity
for this volume.

---

## How the Actioned tickbox works (without mutating Leads)

The original `Leads` tab is **never written to**. Instead:

1. Action Tracker shows leads with no DealID (default) or all leads (toggle).
2. Tick the `Actioned` column, add an optional note, click **Save changes**.
3. For each newly-actioned row, `lib/sheets.append_actioned()` appends to a
   tab called **`Actioned`** with columns
   `actioned_at | email | actioned_by | note`.
4. On the next read, `lib/data.load_leads()` LEFT JOINs the Actioned log
   onto Leads via lowercased email, populating `actioned`, `actioned_at`,
   `actioned_by`, `action_note`.

This keeps the source of truth pristine and gives a full audit trail
("who marked this lead actioned, when, with what note").

---

## Auth + access control

The dashboard delegates login to the **same Supabase project that powers
quay-clock** — staff sign in with their existing clock-in/out username
and PIN. The leads dashboard additionally requires
`is_super = true` OR `is_admin = true` on the staff row (set in the
quay-clock admin UI under Staff → edit → Superuser/Admin).

### Setup

In `.streamlit/secrets.toml`:

```toml
[supabase]
url      = "https://dqszbqiimbfvmmnpgpsb.supabase.co"
anon_key = "eyJ...M9RQnJEidyIMZAwbELTSPakiSnvuWBdHTjD7nuOdCZY"
```

Both values are public (intended for client-side use, gated by Postgres
RLS) — they're the same values committed in
[`quay-clock/quay-config.js`](https://github.com/Twigs002/quay-clock/blob/main/quay-config.js).

### Adding a new user

Add them as a staff member in **quay-clock admin → Staff → New**, then
tick **Superuser** (or **Admin**). They can log into the leads dashboard
immediately with the PIN you assigned.

### Disabling access

Untick Superuser/Admin on the staff row, or set the staff row to
inactive — both take effect on next sign-in.

---

## Future: Meta Lead Bank integration

When Meta hands over the Lead Bank export (Graph API or scheduled CSV
drop), add `app/lib/sources/meta_lead_bank.py` with the same loader
contract:

```python
def load() -> pandas.DataFrame:  # → columns: email, source, datestamp, ...
    ...
```

The aggregation layer is source-agnostic — wire it into `data.load_leads`
as an additional input and the rest of the app works unchanged.

---

## Data quality notes (from the source workbook)

- ~13% of leads have no division assigned (`Division == NaN` or
  `"UPDATED BELOW"` — both are cleaned out on load).
- A small subset of `Datestamp` cells parse with the wrong dayfirst —
  rows more than 7 days in the future are dropped.
- `HubSpot?` column on `RawLeads` is empty for 99%+ of rows; we ignore it.
- `SoldListed.Sold/Leads/Total/Total Spent/Per lead` are populated for
  only one division (Dealmakers). Treat division-level ROI as
  approximate until those cells are filled in across all teams.

---

## Stack

Streamlit · pandas · Plotly · gspread · streamlit-authenticator · bcrypt

---

## License

MIT (see `LICENSE`).
