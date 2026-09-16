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
db/schema.sql         complete database definition (tables + views)
forms/create_observation_form.gs
                      Apps Script that built the observation Google Form;
                      the reference copy of every question and option
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
| `duro` | one row per ~30s sonde reading | **21,000 rows**, Aug 2023 – Oct 2024 | Raw daily CSVs from the Duro UAS sonde, in Drive `Dredger_Duro_Data/1_Raw_CSVs/` (copy into `data/duro/` and run `duro.py`) |
| `cwqt` | one row per weekly Enterococcus sample | **507 rows**, May 2012 – Sept 2026, 6 sites | CWQT Master Data Sheet (citywide program, live) + "Enterococcus at 2nd St" sheet (winter 2023-24, off-season) |
| `turbidity_rta2` | one row per 15-min turbidity reading | **17,409 rows**, Aug 2024 – Aug 2026 | Weekly WQM report PDFs at gowanussuperfund.com (auto-discovered and scraped) |
| `turbidity_rta1` | one row per 15-min turbidity reading | **20,795 rows**, Aug 2023 – Apr 2024 | `GRT_Reports.xlsx` (transcription of the RTA1-era PDFs) + `together_data.xlsx` (fills a Feb–Mar 2024 gap), both hand-downloaded into `data/turbidity_rta1/` |
| `observations` | one row per survey submission | empty (form is live, no responses yet) | Google Form -> response sheet (public), loaded by `observations.py` |
| `tide_predictions` | one row per predicted high/low tide | **22,173 rows**, Jan 2012 – Sept 2027 | NOAA CO-OPS API, station 8517921 (Gowanus Bay). Free, no key |
| `weather` | one row per hour | **~129,000 rows**, Jan 2012 – present | Open-Meteo historical API (ERA5 reanalysis) at the canal. Free, no key |
| `waterbody_advisories` | placeholder (`id` only) | **empty — table not designed** | NYC DEP advisories page + the manually-updated "Advisory Tracker" sheet in Drive |

**Views** (all computed on demand — a view is a saved query, so it is
never "out of date": load new rows and every view reflects them on the
next read): `duro_filtered` (readings at a known site, in water —
reproduces the R pipeline's filter), `site_zones` (site → RTA cleanup
zone, joinable to `duro`, `cwqt` and `observations`),
`daily_site_summary` (per-day/site DO, temperature, salinity, pH stats,
carrying `rta_zone`), `rain_windows`
(rolling 24/48/72-hour rainfall ending at each hour — the join target for
"how much rain fell before this sample", which is what drives CSO
discharges and the bacteria spikes that follow), and `daily_weather`
(daily rain, peak hourly rain, wind). Planned: `turbidity` (long-format
union of both turbidity eras with a `phase` column).

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
- **`weather` is modelled, not measured.** ERA5 reanalysis on a ~9–25 km
  grid. It correlates 0.67 with the Central Park gauge over 450 CWQT
  sample days — close enough for correlation work, but a localised
  cloudburst over the canal can be smoothed away, and those are exactly
  the storms that trigger CSOs. Quote rainfall figures accordingly.
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
   password was amended before it was ever pushed, pushed history
   contains no secrets, and the Supabase password has since been rotated,
   so the string that appears in older local git objects is dead.
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
