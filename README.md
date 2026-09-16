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
  turbidity_rta1.py   local CSV export of GRT_Reports -> turbidity_rta1
  turbidity_rta2.py   RTA2 weekly-report PDFs -> turbidity_rta2
  tide_predictions.py NOAA tide API (OLD STYLE: fetches but writes
                      nothing yet — see "Remaining work")
  observations.py     Google Form responses -> observations
db/schema.sql         complete database definition (tables + views)
forms/create_observation_form.gs
                      Apps Script that built the observation Google Form;
                      the reference copy of every question and option
data/                 local file cache, not part of git: raw inputs named
                      by table (duro/, turbidity_rta2/, ...) plus
                      exports/ — a full CSV snapshot of each table,
                      refreshed automatically after every load
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
| `duro` | one row per ~30s sonde reading | **21,000 rows**, Aug 2023 – Oct 2024 | Raw daily CSVs from the Duro UAS sonde, in Drive `Dredger_Duro_Data/1_Raw_CSVs/` (copy into `data/duro/` and run `duro.py`) |
| `cwqt` | one row per weekly Enterococcus sample | **507 rows**, May 2012 – Sept 2026, 6 sites | CWQT Master Data Sheet (citywide program, live) + "Enterococcus at 2nd St" sheet (winter 2023-24, off-season) |
| `turbidity_rta2` | one row per 15-min turbidity reading | **17,409 rows**, Aug 2024 – Aug 2026 | Weekly WQM report PDFs at gowanussuperfund.com (auto-discovered and scraped) |
| `turbidity_rta1` | one row per 15-min turbidity reading | **20,795 rows**, Aug 2023 – Apr 2024 | `GRT_Reports.xlsx` (transcription of the RTA1-era PDFs) + `together_data.xlsx` (fills a Feb–Mar 2024 gap), both hand-downloaded into `data/turbidity_rta1/` |
| `observations` | one row per survey submission | empty (form is live, no responses yet) | Google Form -> response sheet (public), loaded by `observations.py` |
| `tide_predictions` | one row per predicted high/low tide | **empty — loader not built** | NOAA Tides & Currents API, station 8517921 (Gowanus Bay); `tide_predictions.py` fetches but doesn't load |
| `weather` | one row per weather observation | **empty — loader not built** | Undecided; see "Remaining work" |
| `waterbody_advisories` | placeholder (`id` only) | **empty — table not designed** | NYC DEP advisories page + the manually-updated "Advisory Tracker" sheet in Drive |

**Views** (all computed on demand): `duro_filtered` (readings at a known
site, in water — reproduces the R pipeline's filter), `daily_site_summary`
(per-day/site DO, temperature, salinity, pH stats). Planned: `turbidity`
(long-format union of both turbidity eras with a `phase` column).

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
- **Google Sheets eats leading zeros** — observer IDs are re-padded to 4
  digits by `observations.py`.
- If a Google Form question is reworded, its response-sheet column
  header changes: update `COLUMN_MAP` in `observations.py` and mirror
  the change in `forms/create_observation_form.gs`.

## Remaining work

Empty tables and what fills them:

1. **Turbidity gap, Apr 7 – Aug 12 2024** — no data in either table.
   RTA1 sources stop Apr 6, 2024; the RTA2 weekly reports resume Aug 13.
   Whether this is a genuine monitoring pause between construction
   phases or a missing source is unconfirmed — worth asking GRT.
2. **`tide_predictions`** — rewrite `tide_predictions.py` as a proper loader: fetch
   `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter` (station
   8517921, product `predictions`, interval `hilo`) for a rolling date
   window and upsert. The API is free and public; this is the easiest
   remaining loader.
3. **`weather`** — decide the source first. Candidates: the KNYGOWAN6
   Weather Underground station (what the org used historically; its API
   costs money), NOAA/NWS observations for a nearby station (free), or
   Open-Meteo historical + forecast API (free, no key). The existing
   `weather` table columns mirror a Weather Underground export. Rainfall
   matters most (drives CSO events and bacteria levels).
4. **`waterbody_advisories`** — design the table (current placeholder has
   only `id`), then load from the "Advisory Tracker" sheet in Drive
   (manually maintained, still updated) and/or scrape the NYC DEP
   waterbody-advisories page.
5. **`observations`** — nothing to build; rows appear when people submit
   the form. Consider finalizing the placeholder organism checklists in
   the form (marked TODO in the Apps Script) before promoting it.
6. **CSO events (no table yet)** — Drive has a stale 2013–2023 export of
   the NY Open Data "Combined Sewer Overflows" dataset; a loader could
   pull the live Socrata API instead. Valuable context for bacteria and
   salinity spikes.
7. **NYC DEP Harbor Survey (no table yet)** — a *separate* monitoring
   program from CWQT, with its own long-running DO / bacteria record for
   the canal. Drive's `Other_Water_Data/` has a shortcut ("Gowanus Canal
   Water Quality Testing Data (DEP Harbor Water Quality)") whose target
   this project has not yet opened; DEP also publishes harbor survey data
   on NYC Open Data. Would give the Dredgers' own sonde readings an
   independent agency baseline to compare against.
8. **Duro data catch-up** — `data/duro/` currently holds CSVs through
   Oct 2024. Newer outings (if any) live in Drive
   `Dredger_Duro_Data/1_Raw_CSVs/`; drop them in the folder and re-run.
9. **`turbidity` union view** — add the long-format view over both
   turbidity tables (design agreed, not yet in `schema.sql`).
10. **Automation** — everything currently runs by hand. Plan: a GitHub
   Actions scheduled workflow running `python main.py` (needs the repo
   pushed to GitHub and `.env` values as repo secrets). Credentials are
   clean as of 2026-09-16: the commit that once hardcoded the database
   password was amended before ever being pushed, and pushed history
   contains no secrets. Rotating the Supabase password is still worth
   doing before the repo goes public, since the old string survives in
   the local reflog until garbage collection.
11. **Dashboard** — not started. Supabase's auto-generated REST API or a
    direct Postgres connection (Looker Studio supports Postgres) both
    work; point it at the views, not the tables.
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
