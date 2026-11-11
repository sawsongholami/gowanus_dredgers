# Gowanus Dredgers — Water Quality Data Pipeline

Data pipeline for the [Gowanus Dredgers](https://gowanuscanal.org/) citizen
science program: water quality measurements from the Gowanus Canal
(Brooklyn, NY), collected by volunteers and public monitoring programs,
cleaned and loaded into one Postgres database (Supabase) for analysis and
dashboards.

## Quick links

- Data dictionary: https://docs.google.com/document/d/1yoORQxS0MElzAWmYkUCWYU8MWT_gXfHiYV1-RX_kzG8/edit
- Database schema chart (Lucid): https://lucid.app/lucidchart/57f9fafd-3e17-407f-9c28-7eb63145396b/edit
- SOW: https://docs.google.com/document/d/1zCnLEyLNLX03xW-17WZ1XdRoDxVO3EZpFvhwhjqbOp0/edit
- Shared Drive folder: https://drive.google.com/drive/folders/1AV7SIUhF868zjfiPoFcmEyNCpeQxtbJd
- Observation survey (live Google Form): https://docs.google.com/forms/d/1-UE9hjuBt_GWpDRe1Z4BspCj_s6_ZYLIVvmQpyfTJCM/viewform

## Vocabulary

- **RTA — Remediation Target Area.** EPA's 2013 Record of Decision splits
  the canal into three segments, dredged in sequence: **RTA1** Butler St
  → 3rd St (construction Nov 2020 – summer 2024), **RTA2** 3rd St →
  Hamilton Ave (began June 2024, several years to run), **RTA3** Hamilton
  Ave → Gowanus Bay (not started). The `turbidity_rta1` and
  `turbidity_rta2` tables are therefore *different stretches of canal*
  monitored in sequence, not merely older and newer data — which is
  another reason not to treat a buoy in one as continuous with a
  similarly-named buoy in the other. The `site_zones` view maps every
  monitoring site to its zone.
- **WQM / WQMP** — Water Quality Monitoring (Plan), the GRT programme
  that produces the weekly turbidity reports.
- **GRT — Gowanus Remediation Team**, the contractor consortium running
  the cleanup and publishing at gowanussuperfund.com.
- **CWQT — Citizens' Water Quality Testing**, the citywide volunteer
  Enterococcus sampling programme (SwimmableNYC / Billion Oyster
  Project), source of the `cwqt` table.
- **MPN** — Most Probable Number, the bacteria count unit (per 100 mL).
- **Duro** — the UAS field sonde the Dredgers deploy; source of `duro`.
- **TB** — turning basin, in site names like `Fourth_St_TB`.

## Design principles (read this first)

The pipeline must stay maintainable by people who don't code. Everything
follows from that:

1. **No credentials for reading sources.** Loaders read Google Sheets via
   their public CSV/XLSX export URLs (the sheet must be shared "Anyone
   with the link: Viewer") and public websites directly. The only secret
   is the database password, in a gitignored `.env` file.
2. **Idempotent loaders.** Every loader upserts on its table's primary
   key. Running anything twice — or re-running after a crash — never
   duplicates data. Re-running is always safe.
3. **Flags, not filters.** Raw data is never deleted at load time.
   Questionable readings get flag/label columns (`flag_out_of_water`,
   `site = 'TBD'`, `mpn_raw`); *views* apply the filters.
4. **Views are the interface.** Dashboards read from views
   (`duro_filtered`, `daily_site_summary`), not tables. A view is a saved
   query — no duplicated data, never stale, and table changes stay
   invisible to consumers.
5. **`db/schema.sql` is the single source of truth for the database.**
   Never create or alter tables in the Supabase SQL editor. Edit
   `schema.sql` (idempotent: `CREATE TABLE IF NOT EXISTS` / `CREATE OR
   REPLACE VIEW`) and apply it with `python data_import/apply_schema.py`.
   Note `IF NOT EXISTS` won't reshape an existing table — structural
   changes to a live table need a one-off `ALTER`/migration by hand,
   with `schema.sql` updated to describe the end state.
6. **Provenance columns.** Rows carry `source_file` / `source_report` /
   `source` so any value can be traced back to the file it came from.

## Repo layout

```
data_import/          all runnable Python (loaders import each other as
                      plain same-directory modules — keep them together)
  main.py             runs every loader in sequence; failures are isolated
  apply_schema.py     applies db/schema.sql to Supabase
  write_to_db.py      shared engine + staging-table upsert (casts staged
                      columns to the target table's declared types)
  duro.py             raw Duro sonde CSVs -> duro
  cwqt.py             CWQT master sheet + winter sheet -> cwqt
  turbidity_rta1.py   GRT spreadsheet exports -> turbidity_rta1
  turbidity_rta2.py   RTA2 weekly-report PDFs -> turbidity_rta2
  weather.py          Open-Meteo hourly weather -> weather
  tide_predictions.py NOAA CO-OPS tide predictions -> tide_predictions
  observations.py     Google Form responses -> observations
  advisories.py       Advisory Tracker sheet -> waterbody_advisories
  harbor_survey.py    DEP Harbor Survey (NYC Open Data) -> harbor_survey
  sites.py            db/sites.csv -> sites (run by apply_schema.py)
  apply_app_grants.py re-applies the app login's read grants
db/schema.sql         complete database definition (tables + views)
db/sites.csv          the one list of sites, buoys, survey stations and
                      CSO outfalls, with their locations and RTA zones
dashboard/            the public dashboard (static; see "Dashboard" below)
  build_data.py       views/snapshot -> data/dashboard.{json,js}
  index.html          the page itself
  vendor/             ECharts, vendored so the folder is self-contained
forms/create_observation_form.gs
                      Apps Script that built the observation Google Form;
                      the reference copy of every question and option
app/                  the Streamlit app (see "Streamlit app" below)
  streamlit_app.py    entry point: who is viewing, which pages they get
  access.py           the access rules: which page needs which level
  site_map.py         the canal map that opens under each chart
  assets/             the Dredgers' logo (SVG, top-left corner) and its
                      square PNG copy (browser-tab icon; Safari skips SVG)
  data.py             read-only queries and summaries
  standards.py        the water quality standards (also read by build_data.py)
  app_pages/          one file per page
db/app_reader.sql     one-time setup of the app's read-only login
data_import/viewers.py  add/remove people who can see the app
tests/                access, standards and loader-cleaning tests (pytest tests/)
data/                 local file cache, not part of git. Raw inputs named
                      by the table they feed:
  duro/               229 daily sonde CSVs (the loader's input)
  turbidity_rta1/     GRT_Reports.xlsx + together_data.xlsx (input)
  turbidity_rta2/     113 weekly Superfund report PDFs (input)
  cwqt/               archival copies of the two CWQT sources; the
                      loader reads those sheets live, so these are a
                      safety net, not its input
  exports/            a full CSV snapshot of every table, rewritten
                      automatically after each load (output only —
                      nothing reads these back)
analysis/             ad-hoc analysis scripts
.env                  database credentials (gitignored; see .env.example)
```

## Setup & running

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill in the Supabase credentials
cd data_import
python main.py         # run everything; or run any single loader
python duro.py --dry-run   # every loader supports --dry-run (parse, no write)
```

## Database: tables and views

| Table | Grain | Status (Sept 2026) | Source |
|---|---|---|---|
| `duro` | one row per ~30s sonde reading | **21,000 rows**, Aug 2023 – Oct 2024. **Closed: the sonde is broken** (reported 2026-11-03), no replacement planned | Raw daily CSVs from the Duro UAS sonde, in Drive `Dredger_Duro_Data/1_Raw_CSVs/` (copy into `data/duro/` and run `duro.py`) |
| `cwqt` | one row per weekly Enterococcus sample | **507 rows**, May 2012 – Sept 2026, 6 sites | CWQT Master Data Sheet (citywide program, live) + "Enterococcus at 2nd St" sheet (winter 2023-24, off-season) |
| `turbidity_rta2` | one row per 15-min turbidity reading | **17,409 rows**, Aug 2024 – Aug 2026 | Weekly WQM report PDFs at gowanussuperfund.com (auto-discovered and scraped) |
| `turbidity_rta1` | one row per 15-min turbidity reading | **20,795 rows**, Aug 2023 – Apr 2024 | `GRT_Reports.xlsx` (transcription of the RTA1-era PDFs) + `together_data.xlsx` (fills a Feb–Mar 2024 gap), both hand-downloaded into `data/turbidity_rta1/` |
| `observations` | one row per survey submission | empty (form is live, no responses yet) | Google Form -> response sheet (public), loaded by `observations.py` |
| `tide_predictions` | one row per predicted high/low tide | **22,173 rows**, Jan 2012 – Sept 2027 | NOAA CO-OPS API, station 8517921 (Gowanus Bay). Free, no key |
| `weather` | one row per hour | **~129,000 rows**, Jan 2012 – present | Open-Meteo historical API (ERA5 reanalysis) at the canal. Free, no key |
| `waterbody_advisories` | one row per hand check of DEP's advisory page, per area (inner / outer canal) | **1,438 rows**, May 2024 – June 2026 (2026-11-11) | The project lead's "Advisory Tracker" sheet (link-shared), replaced whole by `advisories.py` daily |
| `harbor_survey` | one row per DEP boat-survey sample at a canal station | **2,723 rows**, 1909 – Dec 2025, stations GC3–GC6 and G2 | NYC Open Data "Harbor Water Quality" (5uug-f49n), upserted by `harbor_survey.py` daily. Free, no key |
| `sites` | one row per place: sampling site, turbidity buoy, Harbor Survey station, CSO outfall | **47 rows** | Copy of `db/sites.csv`, the one version-controlled list; reloaded by `sites.py` whenever the schema is applied |

**Views** (all computed on demand — a view is a saved query, so it is
never "out of date": load new rows and every view reflects them on the
next read): `duro_filtered` (readings at a known site, in water —
reproduces the R pipeline's filter), `site_zones` (site → RTA cleanup
zone, joinable to `duro`, `cwqt` and `observations`; read from `sites`),
`daily_site_summary` (per-day/site DO, temperature, salinity, pH stats,
carrying `rta_zone`), `rain_windows`
(rolling 24/48/72-hour rainfall ending at each hour — the join target for
"how much rain fell before this sample", which is what drives CSO
discharges and the bacteria spikes that follow), and `daily_weather`
(daily rain, peak hourly rain, wind), and `turbidity` (both turbidity
eras in long format, one row per reading per buoy, with a `phase` column).

Canonical site vocabulary: `duro.site` slugs (`Second_St`, `Douglass_St`,
`Ninth_St_Bridge`, ...) assigned from GPS bounding boxes defined in the
Duro Data Dictionary. `cwqt.site` and `observations.site` map into the
same vocabulary so datasets join on site.

## The RTA1 turbidity source files

The RTA1-era weekly report PDFs embed their tables as images, so this era
cannot be scraped. It is loaded instead from spreadsheets that live in
the shared drive's `Other_Water_Data/`, hand-downloaded as `.xlsx` into
`data/turbidity_rta1/`. Three files matter; the first two are the
loader's inputs, the third is a loose end.

**`GRT_Reports.xlsx` — primary input (in the repo).** A transcription of
the RTA1 weekly report PDFs: 15,458 rows, one per 15-minute reading, one
column per buoy (`Ambient`, `W_TB4`, `S_3SB`, `N_USB`, `S_CSB`, `S_USB`,
`N_3SB`), naming the source PDF on every row. Covers Aug 27, 2023 –
Apr 6, 2024, **but contains no rows at all between Feb 4 and Mar 30,
2024.** Missing readings appear as `‐‐` (unicode hyphens) or `--`, and
26 timestamps are duplicated. Prefer this file over the older
`GRT_Reports.csv` / `GRT_long.csv` snapshots in Drive, which stop at
Feb 3, 2024 and lack the `N_3SB` column.

**`together_data.xlsx` — gap filler (in the repo).** Round-the-clock
15-minute readings that cover the Feb–Mar 2024 hole above, contributing
5,363 readings the primary file lacks. Only two of its four columns are
loaded — see the buoy-ambiguity warning in "Data quirks" for why the
other two are deliberately left NULL.

**`GRT_ReportData.xlsx` — not in the repo, not loaded.** 55 rows of
**dissolved oxygen** (mg/L) readings with location labels, Aug–Oct 2023,
extracted from the same RTA1 reports — a different measurement, with no
table designed for it. The local copy was deleted after the Sept 2026
audit; the original remains in Drive as the `GRT_ReportData` spreadsheet.
Re-download it if a DO table ever gets built (see remaining work, where
RTA2-era DO appendices are also noted).

To refresh any of these: open the file in Drive, File > Download >
Microsoft Excel (.xlsx), save into `data/turbidity_rta1/` under the same
name, and re-run `python turbidity_rta1.py`.

## Dashboard

`dashboard/` is a **static** dashboard: one HTML file, one generated data
file, and a vendored copy of the chart library. No server, no database
connection from the browser, no API keys. To publish it, copy the folder
onto a web host.

```bash
python dashboard/build_data.py      # reads the DB; falls back to data/exports/
python -m http.server 8777 --directory dashboard
```

Then open http://localhost:8777. The page also works opened straight off
disk — the data is loaded as a `<script>` rather than `fetch`ed, because
`fetch` from a `file://` page is blocked by the browser.

The generated `dashboard/data/` is git-ignored and not in the repo: this
repo is public, and those files summarise the Dredgers' unpublished Duro
data and CWQT data that belongs to another organisation, so they stay out
until the project lead approves publishing them. Run
`python dashboard/build_data.py` to regenerate them locally.

**The Streamlit side is now built, as one app rather than a pair.** The
plan was a public Streamlit app and a private one. What got built (see
"Streamlit app" below) is a single app in `app/`, hosted on Render, where
Google sign-in decides which pages a viewer sees.
The split is now: this static page as the public-page option, and the
Streamlit app as the team dashboard. Publishing either one waits on the
project lead.

**Why the public page here is static.** Streamlit is a server: to put it
on the Urban Data Response site you would host the app somewhere else and
embed it in an iframe, which means something to keep running, keep paid
for and keep patched, and the free tier sleeps when idle. A static page is
just files — it drops into any CMS or web host, costs nothing, cannot
leak a credential, and has no runtime to maintain. Streamlit earns its
server on the private side, where interactivity and per-viewer access
matter. Hand-written D3 was not worth it for standard charts.

**`build_data.py` is the privacy boundary.** Everything it writes into
`dashboard/data/` becomes public the moment the page is published, so it
emits aggregates only — yearly and per-site summaries, never a table dump
— and reads nothing at all from `observations`, which holds pseudonymous
volunteer submissions. Before this goes on a public site, settle the
question in "Operating notes" above: the Duro sonde readings are the
Dredgers' own unpublished data and the CWQT figures belong to another
organisation. Publishing aggregates of someone else's data, with
attribution, is a different decision from publishing the database, and
it is the org's to make, not the pipeline's.

**It reads the views, not the tables** (`duro_filtered`, `site_zones`), so
a schema change stays invisible to the page. When the database is
unreachable it falls back to the CSV snapshot in `data/exports/` and the
page says so in its header and footer, with the data's as-of date — a
dashboard that silently shows stale numbers is worse than one that admits
it.

## Data quirks an agent/maintainer must know

- **Duro CSVs have two formats.** Pre-Nov-2023: unit-suffixed headers,
  all 17 values present, but the Altitude and Depth *values* are swapped.
  Post-Nov-2023: the sonde stopped recording Altitude but kept the
  header, so rows have 16 values under 17 headers (everything after
  Depth shifts left); missing GPS is `------`. `duro.py` detects format
  per-row by field count.
- **Feb 2024 dissolved-oxygen readings are suspect.** Multiple sites
  average exactly 0.00 mg/L mid-winter (when DO should be at its annual
  high) — almost certainly a dead/frozen DO probe. Not yet flagged in the
  DB; check the "Duro Sonde Calibration Notes" doc in Drive.
- **CWQT MPN values are censored.** `mpn` stores `<10` as 10 and
  `>24196` as 24196; `mpn_raw` preserves the original text. `Trace`
  precipitation is stored as 0.
- **RTA1-era Superfund PDFs cannot be scraped** — their turbidity tables
  are embedded images. That's why the RTA1 era loads from the GRT_Reports
  sheet instead (someone already transcribed them).
- **Early-phase turbidity readings of exactly 0.00 NTU are suspect.**
  533 RTA1 rows (Aug–Sep 2023) and 200 RTA2 rows (Sep–Oct 2024) read
  exactly zero — 1–3% of each era, clustered in the opening weeks, which
  points at instrument commissioning rather than genuinely clear water
  (0.00 NTU is distilled water; the canal's median is 6–7). They drag the
  first weekly medians to near zero. Not flagged in the DB; the dashboard
  plots them as recorded and says so.
- **RTA2 turbidity is weekday-daytime only; RTA1 was round the clock.** RTA1
  readings cover all 24 hours (33% fall between 22:00 and 06:00) and 28% land
  on weekends. RTA2 covers only 07:00–17:00, Monday to Friday: **0% at night,
  0.2% at weekends.** This is operational monitoring during dredging shifts,
  not a continuous environmental record, so the two tables are different kinds
  of measurement on top of being different stretches of canal. Two practical
  consequences. RTA2 is **76% complete against its own schedule** (and 43 of a
  possible 44 readings on a day it runs), so it is not broken — judging it
  against a 24/7 ideal gives a misleading 25%. And the restriction does *not*
  bias the median: applying the RTA2 window to RTA1, which has both, moves the
  median turbidity from 6.31 to 6.30 NTU. Medians are comparable; event capture
  is not, since a plume at night or on a Sunday is invisible in RTA2.
- **Turbidity buoys move and get renamed.** RTA1 era has 7 station
  columns, RTA2 has 3. Whether RTA1 `n_3sb` is the same instrument as
  RTA2 `n3sb` is unconfirmed — do not silently merge them.
- **`together_data.xlsx`'s last two columns are unusable as stations.**
  Its `ambient` and `w_tb4` match `GRT_Reports.xlsx` exactly on every
  shared timestamp, but its `s_csb` and `s3sb` each match a *different*
  GRT column in different periods — they are "whichever southern buoy
  was deployed then," not one station. `turbidity_rta1.py` therefore
  loads only the two trusted columns and leaves the rest NULL for
  gap-fill rows. Roughly 5,300 readings sit unused in that file; they
  are recoverable if someone gets the buoy deployment schedule from GRT.
- **The sonde and the bacteria data barely overlap.** `duro` and `cwqt` share
  only 30 calendar days, and just **15 of those have a matching site**; all
  three of duro/cwqt/turbidity coincide on 16 days. So dissolved oxygen,
  temperature and salinity cannot be related to Enterococcus at any grain —
  not a modelling problem, a scheduling one. Weather and tides, being
  continuous, join to everything. Before designing an analysis, check the
  overlap rather than assuming it.
- **The Duro record is trips, not a time series.** 210 outings over 423 days,
  a median of 37 minutes each, starting around 08:00: **2.7% of elapsed time**,
  all of it in daylight. Daily averages from it are averages of one short
  daytime transect, and the overnight dissolved-oxygen minimum has never been
  observed.
- **Bacteria sampling is weekly, Thursday, and summer.** 96% of `cwqt` samples
  fall May–October and 276 of 292 sample days are Thursdays. One off-season
  winter exists (2023-24, one site, 20 samples). Seasonal and annual claims are
  safe; "year-round" claims are not.
- **Google Sheets eats leading zeros** — observer IDs are re-padded to 4
  digits by `observations.py`.
- **`weather` is modelled, not measured, and not over the canal.**
  Reanalysis has no notion of a point: the API snaps our mid-canal
  request to its own grid, and the cell it serves is centred
  40.6678, −73.9377 — about **4.5 km east-southeast, over inland
  Brooklyn rather than the water**. That cell is the same for every year
  2012–2026 (checked), so the series is at least internally consistent,
  with no location or model discontinuity. It correlates 0.67 with the
  Central Park gauge across 450 CWQT sample days — close, clearly not the
  same measurement. Fine for temperature, humidity and wet-day-versus-dry
  classification, which vary smoothly across a few kilometres. Weaker for
  the thing that matters most here: a summer cloudburst that triggers a
  CSO over Gowanus can miss a cell 4.5 km inland entirely. Quote rainfall
  figures accordingly, and if a published finding ever leans on
  canal-local rain, switch to gauge data (NOAA NCEI Central Park) rather
  than hunting a nearer grid cell — at ~9 km resolution a closer cell
  would feel better without being more local.
- **Rainfall accumulation is computed, never stored.** `weather` holds
  hourly `precipitation_mm`; use the `rain_windows` view for 24/48/72-hour
  antecedent totals rather than adding accumulation columns, so the
  window stays tunable.
- **Tide rows are predictions, not observations** — astronomical highs
  and lows for a station with no sensor, and they extend a year into the
  future, so `max(predicted_at)` is ahead of today by design.
- If a Google Form question is reworded, its response-sheet column
  header changes: update `COLUMN_MAP` in `observations.py` and mirror
  the change in `forms/create_observation_form.gs`.

## Operating notes: secrets, backups, and the bus factor

**Not all of this data is public, and the distinction matters.**

*Public, published by their owners:* the RTA2 turbidity PDFs on
gowanussuperfund.com, NOAA tide predictions, Open-Meteo weather.

*Not public:* the **Duro sonde readings** are the Dredgers' own
unpublished field data. The **GRT_Reports transcription** is Corinne's
work product — the underlying PDFs are public, the transcription is
unpaid labour that is not. The **CWQT master sheet** belongs to another
organisation (SwimmableNYC / Billion Oyster Project) and was shared with
this project, not published by it; the same goes for the **winter
Enterococcus data** processed by the NY Harbor School. The **data
dictionary, calibration notes and SOW** are internal documents.

*Pseudonymous, once it exists:* observation survey responses carry a
self-chosen 4-digit ID rather than a name, but an ID plus a location plus
a timestamp, repeated weekly, can identify a regular volunteer in a small
community. Treat it as pseudonymous, not anonymous.

Practical consequences: `data/` (raw inputs and the `exports/` snapshots
of every table) is gitignored and must stay that way — it holds the
non-public material listed above. Anything republished from `cwqt` needs
attribution to the CWQT programme. And check what a dataset actually is
before putting it somewhere public, rather than assuming the whole
database inherits the Superfund reports' public status.

The controls below are sized to that reality.

- **`.env` is the only secret.** It is gitignored; `.env.example`
  documents the keys. Never commit the real file, and never paste the
  password into a chat, an issue, or a commit message. Rotate it in the
  Supabase dashboard (Settings > Database > Reset database password) if
  it is ever exposed — rotation is quick and invalidates every stale
  copy at once. Last rotated 2026-09-16.
- **Back up before schema changes.** This is the real gap. Anyone with
  the `.env` has full rights to drop and recreate tables, and several
  tables in this repo have been reshaped that way. Take a Supabase
  backup (or confirm the table is empty, as the reshapes here did)
  before running a migration, because nothing else stands between a
  mistake and the data.
- **Consider a second Supabase project as a dev target** if the schema
  starts changing often. Free tier; point `.env` at it while testing a
  loader, then switch back. Equivalent cheaper step: a read-only
  database role for exploration, keeping the full-rights role for
  deliberate migrations.
- **When automating, secrets go in GitHub Actions secrets**, never in
  the workflow file. Prefer a Supabase key scoped to what the job needs
  (inserts) over the full database password.
- **Working with an AI agent on this repo:** `auto` permission mode is
  fine for the read-edit-run loop and makes the work far faster, but it
  also means file deletions and schema drops happen without a prompt.
  Use a mode that asks before destructive steps, or ask the agent to
  state what it is about to delete and why it is recoverable.
- **The bus factor is the biggest real risk, not a breach.** The
  failure mode for a volunteer project is that the one person who
  understands the pipeline moves on and the org drifts back to
  spreadsheets — which is what happened to the R scripts this pipeline
  replaced. Mitigation: have a second person run `python main.py` from a
  clean clone before that knowledge lives in one head, and keep this
  README honest about what is verified versus assumed.

## Streamlit app

`app/` is the team's dashboard, hosted free on Render at
https://gowanus-dredgers.onrender.com. It reads Supabase live, so it is
current as soon as a loader runs.

**Why Render, not Streamlit Community Cloud.** Community Cloud deploys
only through a GitHub sign-in that grants it admin rights over webhooks
on every repo the account administers, plus read access to its
organisations, with no way to narrow it. On an account that also belongs
to a work organisation, that reaches into the employer's repos. Render
connects through a GitHub App that can be installed on this one repo
only. The trade-off: Render's free tier sleeps after about 15 idle
minutes, so the first visit after a quiet spell takes ~30 seconds.

**Why the build swaps Streamlit's tab icon** (2026-11-10). Streamlit's
page arrives with its own icon and only switches to the app's `page_icon`
once the app has run, so a slow start or Safari showed Streamlit's logo.
Render's build command therefore runs `app/install_tab_icon.py`, which
copies the Dredgers' icon over Streamlit's file in the installed package.
Editing an installed library is normally avoided, since an upgrade can
quietly undo it; here every build reruns it, the script fails the build if
the file moves, and `tests/test_tab_icon.py` checks the same. The worst
case is the old behaviour.

**What's in it** (reworked 2026-11-10 after the team's first review).
Each page is framed as a question and explains its charts in plain
language: *Is the canal safe to swim in?* (Enterococcus by year with each
year's geometric mean, a one-year view, rain, tide at sampling time, and
sites, and the city's Harbor Survey beside CWQT), *Can fish survive in
the canal?* (dissolved oxygen, with the city's survey beside the sonde),
*How much does dredging cloud the water?* (turbidity), and *Explore the
data*, which puts any of the datasets side by side as one number per day.
Bacteria are summarised with the geometric mean, the convention for
Enterococcus, not the median.
**Swim standards** (decided 2026-11-11 with the project lead): New York
State's bathing-beach rules (10 NYCRR Subpart 6-2, also NYC's): no single
sample over 104 MPN, and a 30-day geometric mean of five or more samples
no higher than 35. Single samples are judged against 104 only;
geometric means get CWQT's rating, good (35 or less), advisory (up to
104) or poor (over 104), as on their charts page. This replaced an
earlier 110 MPN line labelled as EPA's Beach Action Value. The page's
"Did it pass the state's 30-day test?" section applies 35 the way the state
does: for each site and sampling day, the geometric mean of that site's
samples over the 30 days ending that day, counted only when the window
holds five or more samples (`data.rolling_geo_mean`). All the standards
(and the 5 mg/L oxygen line) live once, in `app/standards.py`, which the
static page's `build_data.py` imports too. A map of the monitoring sites opens under
each chart with that chart's sites picked out (`app/site_map.py`; the
street map behind it is loaded from CARTO by the viewer's browser, which
the Privacy page says).

**Who sees what.** Visitors sign in with Google. The `app_viewers` table
lists who may see the private pages (`team`) and who may also see the
viewer list (`admin`); everyone else, signed in or not, gets only the
public pages. `app/access.py` says which page needs which level. Today only
the About page is public: publishing anything derived from the Duro or
CWQT data waits on the project lead (see "Operating notes" above). To
publish a page, change its level to `'public'` in `access.py`.
The viewer list page ("Who can see this") stays separate from the public
Privacy page (decided 2026-11-11): it shows real email addresses, so it
stays admin-only, while Privacy has to be open to anyone for Google
sign-in. Privacy describes the list in general terms instead.

```bash
cd data_import
python viewers.py add someone@gmail.com team "Dredgers board"
python viewers.py remove someone@gmail.com
python viewers.py list
```

**Why the gate is in the app, not the host.** Normally the host blocks
strangers before they reach the app, and the app checks again. Here that
host-level gate is either paid (Streamlit only allows one private app,
invite-only through its website) or needs a Google Workspace organisation
(Cloud Run's IAP), so the app's own check is the only barrier. That is
a deliberate trade-off, and it is why:

- a page the viewer can't see is never registered with `st.navigation`,
  so it has no URL; each page also re-checks at the top;
- everything fails closed (unknown page, unknown role, unverified email or
  an unreachable viewer list all mean public);
- the app connects as `app_reader`, a read-only login with no access to
  `duro` or `observations` (`db/app_reader.sql`), never the owner login
  in `.env`;
- `tests/test_app_access.py` checks that signed-out and unlisted viewers
  can't open a private page and never trigger a data query. Run it after
  any change to `app/`, and keep `observations` off the app until there is
  a reason to show it.

**Running it locally.** Streamlit needs Python 3.11 or newer (the loaders'
venv is 3.9, so use a separate one). From the repo root:

```bash
python3.12 -m venv venv-app
venv-app/bin/pip install -r app/requirements.txt pytest
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # fill it in
venv-app/bin/pytest tests/
venv-app/bin/streamlit run app/streamlit_app.py
```

**One-time setup** (all done 2026-11-03; kept as the record of how, and
for rebuilding it elsewhere):

1. **Check Supabase is awake.** Free projects pause after a week without
   activity, and a paused project makes the app (and every loader) fail.
   Restore it from the Supabase dashboard if needed.
2. **Create the viewer table:** `python data_import/apply_schema.py`.
3. **Create the read-only login:** open `db/app_reader.sql`, paste it into
   the Supabase SQL editor with a new long random password in place of the
   placeholder, and run it. Save the password only in the Secrets below.
   Later grant changes (a new table for the app) don't need the editor:
   `python data_import/apply_app_grants.py` re-runs everything below the
   `CREATE ROLE` line.
4. **Add yourself:** `python data_import/viewers.py add you@gmail.com admin`.
5. **Google sign-in.** In Google Cloud Console, create a project; under
   *Google Auth Platform*, set up the consent screen (External; scopes
   `openid`, `email`, `profile`). Then create an OAuth client
   (*Web application*) with two authorised redirect URIs:
   `http://localhost:8501/oauth2callback` and
   `https://gowanus-dredgers.onrender.com/oauth2callback`. While the consent
   screen is in *Testing*, only people listed as test users can sign in.
   To **publish it to production**, Google wants, on the *Branding* page:
   home page `https://gowanus-dredgers.onrender.com`, privacy policy
   `https://gowanus-dredgers.onrender.com/privacy` (the app's public
   Privacy page), and authorised domain `gowanus-dredgers.onrender.com`
   (allowed because `onrender.com` is on the public suffix list, so each
   app's address counts as its own domain). Leave the logo empty:
   uploading one triggers Google's verification review.
   **The app deliberately stays in Testing, not published**: Google then
   refuses sign-in to anyone not on its *Audience > Test users* list, a
   second lock in front of the app's own viewer list. So each viewer is
   added in both places (test users, then `viewers.py add`) and removed
   from both. Test users see a one-time "Google hasn't verified this app"
   screen and click *Continue*. Because the app asks only for name, email
   and profile, Testing's 7-day sign-in expiry doesn't apply. Publish only
   if the list outgrows hand upkeep (cap: 100 test users); the viewer list
   alone still guards the data.
6. **Deploy on Render.** Sign up at render.com with your Gmail (not
   "Sign in with GitHub"). *New > Web Service > GitHub*; when GitHub asks
   where to install the Render app, pick your personal account and **Only
   select repositories > this repo**. Then:
   - Name `gowanus-dredgers`, branch `main`, region Ohio (next to
     Supabase), language Python 3, instance type Free.
   - Build command: `pip install -r app/requirements.txt && python
     app/install_tab_icon.py` (the second part puts the Dredgers' icon
     in place of Streamlit's own, so the browser tab shows it from the
     first moment, not only once the app has loaded)
   - Start command: `streamlit run app/streamlit_app.py --server.port
     $PORT --server.address 0.0.0.0 --server.headless true
     --secrets.files /etc/secrets/secrets.toml`
   - *Environment*: variable `PYTHON_VERSION` = `3.12.7`; and a *Secret
     File* named `secrets.toml` holding your filled-in
     `.streamlit/secrets.toml`, with `redirect_uri` changed to the
     deployed address.
   - *Settings > Health Check Path*: `/_stcore/health`.
   Leave the service public: the sign-in decides who sees data.
7. **Check it:** open the app in a private window (only About should
   show), then sign in.

Pushes to the deployed branch redeploy the app automatically. Secrets and
settings live only in the Render dashboard, so they are the one part an
agent can't change.

## Remaining work

Empty tables and what fills them:

1. **Confirm the RTA zone boundaries** (small). `site_zones` assigns each
   site to a cleanup area by applying the published street boundaries to
   its latitude. Four sites sit within ~50 m of a line — `Third_St`,
   `Bond_St`, `WholeFoodsWest` at the 3rd St boundary and
   `Hamilton_Bridge` at the Hamilton Ave one — and EPA states RTA1
   includes part of the 5th Street turning basin, which lies south of
   3rd St, so the real boundary is not a clean latitude cut. Check them
   against EPA's own RTA figure before any finding leans on them.
2. **Rainfall precision (optional upgrade).** `weather` is ERA5
   reanalysis on a grid, not a Gowanus rain gauge. Against the CWQT
   program's own Central Park figures it correlates 0.67 across 450
   sample days — the same weather, not the same measurement. If
   gauge-accurate local rainfall ever matters more than convenience,
   NOAA NCEI's Central Park record (free, needs a token) is the upgrade,
   and is the gauge CWQT itself uses. Avoid reviving the KNYGOWAN6
   Weather Underground route: the API costs money and the old manual
   workflow was error-prone by its author's own admission.
3. **Observed water level (optional).** `tide_predictions` holds
   *astronomical predictions* for station 8517921, which has no sensor.
   For storm surge — plausibly relevant to CSO and fish-kill events —
   the nearest real gauge is The Battery (8518750, product
   `water_level`); the same loader would extend to it.
4. **`waterbody_advisories`** — done (2026-11-11), from the Advisory
   Tracker sheet. Its last entry is June 2026, so the log has gone quiet.
   **Ask Corinne** whether anyone still keeps it; if not, scraping DEP's
   waterbody-advisory page daily is the replacement. The sheet's "Flushing Tunnel" tab (daily % open, Aug
   2025 on) is not loaded yet: its early dates lack a year.
5. **`observations`** — nothing to build; rows appear when people submit
   the form. Consider finalizing the placeholder organism checklists in
   the form (marked TODO in the Apps Script) before promoting it.
6. **CSO events — no source found (checked 2026-11-11).** The NY Open
   Data "Combined Sewer Overflows" dataset (ephi-ffu6, and the Drive copy
   of it) is a 2015 list of outfalls, not events; for NYC's outfalls it
   only says "visit facility website". Its 16 Gowanus outfalls are now in
   `db/sites.csv` (kind `cso outfall`). The closest event record we have
   is `waterbody_advisories`: DEP posts an advisory when it models an
   overflow. Event data would have to come from DEP directly.
7. **NYC DEP Harbor Survey** — loaded (2026-11-11) into `harbor_survey`
   from NYC Open Data, and charted: the oxygen page sets its near-surface
   oxygen beside the sonde, the bacteria page its yearly geometric mean
   beside CWQT, and the explorer has both as datasets. It is always the
   third palette colour (aqua) so it reads as the same source everywhere.
8. **Duro is closed.** The sonde broke (reported 2026-11-03) and no
   replacement is planned, so `duro` (Aug 21, 2023 – Oct 18, 2024) is now a
   finished historical dataset. One last check before calling it final: look
   in Drive `Dredger_Duro_Data/1_Raw_CSVs/` for any outing after Oct 18,
   2024; if there is one, drop it in `data/duro/` and re-run `duro.py`. If a
   new instrument arrives, check its file format against the two Duro
   formats in "Data quirks" before reusing `duro.py`.
9. **`turbidity` union view** — done (2026-11-03); see the views above.
10. **Automation** — `.github/workflows/daily_load.yml` runs the seven
   loaders whose sources are online (cwqt, turbidity_rta2, weather,
   tide_predictions, observations, advisories, harbor_survey) every day at
   10:00 UTC, which also keeps the free Supabase project from pausing.
   Free on a public repo.
   It needs the four `.env` values as repository secrets, and GitHub only
   runs a schedule from the default branch. A failed loader fails the run
   and GitHub emails the owner. Since 2026-11-11 every loader downloads
   through `data_import/web.py`, which retries timeouts and temporary
   server errors (waiting 0, 10, 20, 40 s) and gives each download a time
   limit, after an Open-Meteo timeout failed that day's weather step.
   duro and turbidity_rta1 still run by hand:
   their inputs are files downloaded into `data/`. GitHub switches off a
   public repo's schedules after 60 days without a commit (it emails
   first; one click turns it back on). Credentials are
   clean as of 2026-09-16: the commit that once hardcoded the database
   password was amended before it was ever pushed, pushed history
   contains no secrets, and the Supabase password has since been rotated,
   so the string that appears in older local git objects is dead.
11. **Dashboards** — two first versions built; see "Dashboard" and
    "Streamlit app" above. The static page in `dashboard/` is the
    public-page option: plain files that drop onto any web host. The
    Streamlit app in `app/` is the team dashboard, with Google sign-in,
    live on Render since 2026-11-03 for the four-person team (all admin;
    Google test users plus the viewer list). Publishing either one waits
    on the project lead's OK for the Duro and CWQT data, and the club
    wants to read the chart pages through before they go public (project
    lead, 2026-11-11). Asked her on 2026-11-11, waiting on a reply: who
    does the read-through (their Google emails, to add as viewers), and
    whether CWQT's data can be published or SwimmableNYC and Billion
    Oyster Project need asking first. Still open:
    - refreshing the static page's data automatically: waits on the
      publishing OK. Its data file is a summary of the Duro and CWQT data,
      and the only places a scheduled job could put it (a commit to this
      public repo, or a public host) would publish it;
    - the About page now carries the partners' draft website copy (the
      "Dashboard / Website Copy" tab of the SOW doc). Its figures (CSO
      gallons, apartment counts, tank sizes and dates, the August 2024
      flushing-tunnel jump) are theirs and unchecked against a source;
      confirm before the page goes public (asked Arpan, 2026-11-11);
    - put Dentons Pond on the map: its outfall sampling site is somewhere
      near Whole Foods; the project lead is asking Eymund for the spot.
      (Lowlands is placed, from the lead's pin. The two ambient turbidity
      buoys are placed approximately, from the weekly reports' "Buoy
      Locations" text: RTA1's in the eastern end of the Fourth St Turning
      Basin, RTA2's just north of Carroll St Bridge; see `BUOYS` in
      `db/sites.csv`.);
12. **RTA2 gaps (optional).** 17 of the 113 RTA2 report PDFs yielded no
    rows: weeks 1–8 (Jun–Aug 2024) use an earlier table layout with a
    `9SB` station and merged cells that defeat extraction (recoverable
    with parser work); a few holiday/shutdown weeks genuinely have no
    tables; and a handful (weeks 60, 64–65, 80, ...) have image-rendered
    appendices, OCR-only. Early RTA2 reports also carry an Appendix B
    with **Dissolved Oxygen** tables (Ambient/9SB) that nothing captures
    yet — a candidate future table.
13. **The R scripts in Drive (`R_scripts/`) are retired.** The Duro
    combine/label/filter script is fully superseded by `duro.py` +
    `duro_filtered`; the weather import script's manually-pasted-
    spreadsheet mechanism should not be revived (see `weather` above),
    though its wind-name→degrees mapping is worth porting.
14. **Share ownership of the hosting accounts.** As of 2026-11-03 the
    GitHub repo, Render (billed to the maintainer's card), Supabase and the
    Google Cloud project all sit in the maintainer's personal accounts.
    Invite the project lead to each (GitHub collaborator, Render workspace
    member, Supabase project member, Google Cloud project owner) so the
    dashboard survives a handover; longer term, move them under a
    Gowanus Dredgers organisation account.

## Drive sources already ruled out (audited 2026-09-16)

So nobody re-investigates these. In the shared drive's
`Other_Water_Data/` (16 files, fully enumerated):

- `2023_CWQT_ALLSITES_Reformatted` and `2024_CWQT` are **derivatives** of
  the CWQT Master Data Sheet, not independent data — already covered by
  `cwqt.py`. `Enterococcus at 2nd St` is the one genuinely unique
  Enterococcus source and is loaded.
- The `GRT_*` and `together_*` files are **RTA1 turbidity**, not CWQT —
  see "The RTA1 turbidity source files" above for which two are the
  loader's inputs and why. The remaining variants (`GRT_Reports.csv`,
  `GRT_long.csv`, `together_data.csv`, `together_long.csv`,
  `together_long.xlsx`) are older or reshaped copies carrying no data
  the loaded pair lacks; that was verified against the database, not
  assumed. `GRT_ReportData.xlsx` is dissolved oxygen, not turbidity.
- The doc titled `https://gowanussuperfund` is just a bookmark to the
  monitoring-data page the scraper already reads.
- **Unresolved:** two Drive *shortcuts* — "2023 CWQT: ALL SITES" and the
  DEP Harbor Water Quality one — whose targets the Drive connector
  cannot follow. The first was created 52 seconds after
  `2023_CWQT_ALLSITES_Reformatted` with a matching name, so it is almost
  certainly the same source, but that is inference, not verification.
  Open them by hand to confirm.

## Manual steps outside this repo (for the record)

- Google Form + response sheet live in the owner's My Drive and should be
  moved into the shared drive's `Observational Survey` folder; the Apps
  Script project ("Untitled project") should be renamed. (The Drive
  connector used by the AI agent had read-only access at the time.)
- The response spreadsheet is already shared "Anyone with link: Viewer"
  (required by `observations.py`). GRT_Reports is deliberately NOT
  link-shared; its loader reads a hand-downloaded CSV instead.
- Set up 2026-11-03 for the app and daily load: the `app_reader` login's
  password (set by hand in the Supabase SQL editor; it lives only in the
  app's secret file on Render and the maintainer's local
  `.streamlit/secrets.toml`), the four `SUPABASE_DB_*` repository secrets
  on GitHub (Settings > Secrets and variables > Actions), a Google Cloud
  project with the OAuth client for sign-in, and the Render service (its
  GitHub App installed on this repo only). The workflow file itself was
  added through the GitHub website.
- Changed 2026-11-10 in Render: the build command also runs
  `python app/install_tab_icon.py` (see "Streamlit app"). Render doesn't
  rebuild when a setting changes, so it took a manual deploy to apply.
- The GitHub login AI agents use on the owner's Mac is a fine-grained
  token limited to this repo: it can push code and open and merge pull
  requests, but cannot change workflows, secrets or settings, or start
  Actions runs. Those are done by the owner in the browser.
