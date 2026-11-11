-- Gowanus Dredgers database schema: the single source of truth.
--
-- Every statement here is idempotent (CREATE TABLE IF NOT EXISTS /
-- CREATE OR REPLACE VIEW), so the whole file is safe to run repeatedly.
-- Apply it with:
--     python data_import/apply_schema.py
-- (the loaders also apply it automatically before writing).
--
-- Do not create or alter tables in the Supabase SQL editor directly --
-- edit this file and apply it, so the schema stays versioned in git.

------------------------------------------------------------------------
-- Duro sonde readings, one row per ~30s sample, loaded by duro.py from
-- the raw daily CSV exports. (Replaced the original Lucid-chart `duro`
-- design, dropped 2026-09-15.) Rows are never filtered out at load time:
-- questionable readings are flagged (flag_out_of_water) or labeled
-- (site is NULL = no GPS fix, 'TBD' = GPS outside every known site box).
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS duro (
    observed_at       timestamp PRIMARY KEY,
    water_temp_c      double precision,
    ph                double precision,
    orp_mv            double precision,
    ec_us_cm          double precision,
    tds_ppm           double precision,
    salinity_ppt      double precision,
    specific_gravity  double precision,
    do_mg_l           double precision,
    do_sat_pct        double precision,
    pressure_mbar     double precision,
    air_temp_c        double precision,
    depth_m           double precision,
    latitude          double precision,
    longitude         double precision,
    site              text,
    flag_out_of_water boolean,
    source_file       text
);

------------------------------------------------------------------------
-- Gowanus Superfund construction turbidity monitoring (NTU, 15-minute).
-- turbidity_rta1: the RTA1 era (~2020 - early 2024), loaded by
--   turbidity_rta1.py from the GRT_Reports Google Sheet (a transcription of
--   the era's PDFs, whose tables are images and cannot be text-scraped).
--   One column per monitoring buoy; buoys moved over the project, so
--   most columns are NULL in any given period.
-- turbidity_rta2: the RTA2 era (2024 - present), scraped from the weekly
--   report PDFs at gowanussuperfund.com by turbidity_rta2.py.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS turbidity_rta1 (
    date          date,
    time          time,
    ambient       double precision,
    w_tb4         double precision,
    s_3sb         double precision,
    n_usb         double precision,
    s_csb         double precision,
    s_usb         double precision,
    n_3sb         double precision,
    source_report text,
    PRIMARY KEY (date, time)
);

CREATE TABLE IF NOT EXISTS turbidity_rta2 (
    date          date,
    time          time,
    ambient       double precision,
    n3sb          double precision,
    tb4           double precision,
    source_report text,
    PRIMARY KEY (date, time)
);

------------------------------------------------------------------------
-- NOAA astronomical tide predictions, one row per high or low tide,
-- loaded by tide_predictions.py from the NOAA CO-OPS API. Station 8517921
-- (Gowanus Bay) is a prediction-only station: these are predicted heights
-- above MLLW, not measured water levels. Predictions extend into the
-- future, so max(predicted_at) is normally ahead of today.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tide_predictions (
    predicted_at timestamp PRIMARY KEY,
    height_m     double precision,
    tide_type    text,   -- 'H' (high) or 'L' (low)
    station      text
);

------------------------------------------------------------------------
-- Tables below were designed in the Lucid chart and created ahead of
-- their loaders; their shapes may still change when the loaders get
-- written.
------------------------------------------------------------------------
------------------------------------------------------------------------
-- CWQT Enterococcus sampling at the two Gowanus sites, loaded by cwqt.py
-- from two sources: the citywide CWQT Master Data Sheet (regular seasons,
-- 2012-present, live) and the "Enterococcus at 2nd St" sheet (winter
-- 2023-24 off-season sampling). mpn holds censored values at their bound
-- ('<10' -> 10, '>24196' -> 24196); mpn_raw preserves the original text.
-- 'Trace' precipitation is stored as 0.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cwqt (
    date                           date,
    site_id                        integer,
    site                           text,  -- Second_St / Lowlands, joins duro.site
    site_name                      text,  -- the program's full site name
    sample_time                    time,
    mpn                            double precision,
    mpn_raw                        text,
    battery_high_tide              time,
    precip_on_collection_day       double precision,
    precip_1_day_before_collection double precision,
    precip_2_days_before_collection double precision,
    precip_3_days_before_collection double precision,
    precip_4_days_before_collection double precision,
    precip_5_days_before_collection double precision,
    precip_6_days_before_collection double precision,
    notes                          text,
    source                         text,  -- 'cwqt_master' or 'winter_2nd_st'
    PRIMARY KEY (date, site_id)
);

------------------------------------------------------------------------
-- Hourly weather for the canal, loaded by weather.py from the Open-Meteo
-- historical API (ERA5 reanalysis). NOTE: reanalysis is modelled on a
-- grid, not measured at a Gowanus rain gauge -- good for correlation,
-- but a localised summer cloudburst can be smoothed away.
-- Accumulation is deliberately NOT stored: sum precipitation_mm over
-- whatever window matters (see the rain_windows view).
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weather (
    observed_at        timestamp PRIMARY KEY,
    temperature_c      double precision,
    dew_point_c        double precision,
    humidity_pct       double precision,
    precipitation_mm   double precision,  -- rain + snow water equivalent
    rain_mm            double precision,
    wind_speed_kmh     double precision,
    wind_direction_deg double precision,
    wind_gusts_kmh     double precision,
    pressure_hpa       double precision,
    solar_wm2          double precision
);

------------------------------------------------------------------------
-- Monitoring sites: a copy of db/sites.csv, the one version-controlled
-- list, replaced whole by data_import/sites.py (which apply_schema runs).
-- Edit the CSV, never this table. Duro sites have a GPS box; others have
-- a single pin (lat/lon); lat/lon is the box centre where there is a box.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sites (
    site      text PRIMARY KEY,   -- slug as stored in duro.site / cwqt.site
    kind      text NOT NULL,      -- 'sampling site' or 'turbidity buoy'
    rta_zone  text,
    lat_min   double precision,
    lat_max   double precision,
    lon_min   double precision,
    lon_max   double precision,
    lat       double precision,
    lon       double precision,
    source    text,
    note      text
);

------------------------------------------------------------------------
-- NYC DEP wet-weather advisories for the canal, as checked by hand and
-- logged in the project lead's "Advisory Tracker" sheet (May 2024 on).
-- One row per check per area: DEP posts "Gowanus Canal, Inner" and
-- "Outer" separately. Replaced whole by data_import/advisories.py on every
-- run (the sheet is hand-edited and has no stable key); sheet_row points
-- back to the line in the sheet. Times are New York local.
-- (Replaced an empty placeholder with only an id column, 2026-11-11.)
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS waterbody_advisories (
    sheet_row               integer PRIMARY KEY,
    check_date              date NOT NULL,
    checked_at              timestamp,  -- DEP page's server time when checked
    area                    text NOT NULL,  -- 'inner' or 'outer'
    on_advisory             boolean,    -- NULL: not recorded
    advisory_until          timestamp,  -- end time DEP gave, when on advisory
    rain_gauge              text,       -- DEP's gauge code, e.g. 'RH'
    emailed                 boolean,    -- whether an advisory email went out
    info_text               text,       -- raw "Advisory Info" text
    notes                   text,
    flushing_tunnel_status  text        -- raw, as logged
);

------------------------------------------------------------------------
-- NYC DEP Harbor Survey samples at the canal's stations (GC3-GC6, G2 and a
-- few one-off 2000-2003 stations), from NYC Open Data 5uug-f49n, 1909 on.
-- DEP's own boat survey, independent of CWQT and the Dredgers' sonde.
-- Loaded by data_import/harbor_survey.py, upserted on the source row id.
-- Bacteria in cells/100 mL ("<10" stored as 10); top = near surface,
-- bottom = near the bed. Station locations are in db/sites.csv.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harbor_survey (
    obs_id                  text PRIMARY KEY,   -- the dataset's :id
    station                 text NOT NULL,
    sample_date             date NOT NULL,
    sample_time             time,
    weather                 text,               -- 'dry' or 'wet', DEP's call
    site_depth_ft           double precision,
    top_temp_c              double precision,
    bottom_temp_c           double precision,
    top_salinity_psu        double precision,
    bottom_salinity_psu     double precision,
    top_do_ctd_mg_l         double precision,   -- CTD profiler
    bottom_do_ctd_mg_l      double precision,
    top_do_winkler_mg_l     double precision,   -- Winkler titration
    bottom_do_winkler_mg_l  double precision,
    top_do_sat_pct          double precision,
    bottom_do_sat_pct       double precision,
    secchi_depth_ft         double precision,
    top_ph                  double precision,
    bottom_ph               double precision,
    top_enterococci         double precision,
    bottom_enterococci      double precision,
    top_fecal_coliform      double precision,
    bottom_fecal_coliform   double precision,
    top_tss_mg_l            double precision,
    bottom_tss_mg_l         double precision,
    top_chlorophyll_a_ug_l  double precision,
    lat                     double precision,   -- this visit's position, when logged
    lon                     double precision
);

------------------------------------------------------------------------
-- Volunteer observation survey submissions, one row per Google Form
-- response, to be loaded from the form's linked response spreadsheet
-- (created by forms/create_observation_form.gs). Checkbox answers are
-- stored as the comma-separated strings the sheet produces.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS observations (
    submitted_at     timestamp,  -- the form's own response timestamp
    observer_id      text,
    location         text,       -- dropdown choice; NULL if "somewhere else"
    site             text,       -- canonical site slug, joinable with duro.site
    latitude         double precision,
    longitude        double precision,
    observed_date    date,
    observed_time    time,
    litter           text,
    dead_organisms   text,
    living_organisms text,
    water_appearance text,
    oil_sheen        text,
    smells           text,
    sounds           text,
    notes            text,
    PRIMARY KEY (submitted_at, observer_id)
);

------------------------------------------------------------------------
-- Who may see the Streamlit app's private pages (app/access.py). One row
-- per Google account; anyone not listed sees only the public pages.
-- Managed with data_import/viewers.py. Emails are stored lower-case.
-- Row-level security is on with no policy for Supabase's anon and
-- authenticated roles, so the public REST API can't list these emails;
-- db/app_reader.sql grants the app's read-only login a policy to read it.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_viewers (
    email    text PRIMARY KEY CHECK (email = lower(email)),
    role     text NOT NULL CHECK (role IN ('team', 'admin')),
    note     text,         -- who they are / why they have access
    added_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE app_viewers ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------------------
-- Views: computed on demand, no data duplicated. Dashboards should read
-- from views rather than tables, so table changes stay invisible to them.
------------------------------------------------------------------------

-- Reproduces the filter semantics of Corinne's Dredger_WQ_CombineDuroFiles.R:
-- only readings at a known site (drops no-GPS rows and rows outside every
-- site bounding box), plus the out-of-water flag from the data dictionary.
CREATE OR REPLACE VIEW duro_filtered AS
SELECT *
FROM duro
WHERE site IS NOT NULL
  AND site <> 'TBD'
  AND NOT flag_out_of_water;

-- Which EPA Remediation Target Area each monitoring site sits in. The
-- 2013 Record of Decision splits the canal into three segments dredged in
-- sequence: RTA1 Butler St to 3rd St (built Nov 2020 - summer 2024),
-- RTA2 3rd St to Hamilton Ave (began June 2024), RTA3 Hamilton Ave to
-- Gowanus Bay (not started). Join this to duro.site / cwqt.site /
-- observations.site to group readings by cleanup phase.
--
-- The zones live in db/sites.csv with the rest of each site's details
-- (loaded into `sites` by data_import/sites.py). Assignments apply the
-- published street boundaries to each site's latitude. Three sites sit within ~50 m of a boundary and should be
-- confirmed against EPA's own RTA figure before anything load-bearing
-- rests on them: Third_St and Bond_St (called RTA1 here) and
-- WholeFoodsWest (called RTA2) straddle the 3rd St line, and
-- Hamilton_Bridge sits exactly on the RTA2/RTA3 line. EPA also states
-- RTA1 includes part of the 5th Street turning basin, which is south of
-- 3rd St -- so the true boundary is not a clean latitude cut.
CREATE OR REPLACE VIEW site_zones AS
SELECT site, rta_zone
FROM sites
WHERE kind = 'sampling site' AND rta_zone IS NOT NULL;

-- Per-day, per-site summary for dashboards. Built on the filtered view so
-- out-of-water and unlocated readings never skew the stats.
CREATE OR REPLACE VIEW daily_site_summary AS
SELECT
    observed_at::date                     AS date,
    d.site,
    z.rta_zone,
    count(*)                              AS n_readings,
    round(avg(do_mg_l)::numeric, 2)       AS avg_do_mg_l,
    round(min(do_mg_l)::numeric, 2)       AS min_do_mg_l,
    round(max(do_mg_l)::numeric, 2)       AS max_do_mg_l,
    round(avg(water_temp_c)::numeric, 2)  AS avg_water_temp_c,
    round(avg(salinity_ppt)::numeric, 2)  AS avg_salinity_ppt,
    round(avg(ph)::numeric, 2)            AS avg_ph
FROM duro_filtered d
LEFT JOIN site_zones z ON z.site = d.site
GROUP BY observed_at::date, d.site, z.rta_zone;

-- Rolling rainfall totals ending at each hour. This is the join target
-- for "how much rain fell before this sample": CSO discharges, and the
-- bacteria spikes that follow them, track antecedent rainfall rather
-- than the rain falling at the moment of sampling.
CREATE OR REPLACE VIEW rain_windows AS
SELECT
    observed_at,
    precipitation_mm,
    round(sum(precipitation_mm) OVER w24::numeric, 2) AS rain_24h_mm,
    round(sum(precipitation_mm) OVER w48::numeric, 2) AS rain_48h_mm,
    round(sum(precipitation_mm) OVER w72::numeric, 2) AS rain_72h_mm
FROM weather
WINDOW
    w24 AS (ORDER BY observed_at RANGE BETWEEN INTERVAL '23 hours' PRECEDING AND CURRENT ROW),
    w48 AS (ORDER BY observed_at RANGE BETWEEN INTERVAL '47 hours' PRECEDING AND CURRENT ROW),
    w72 AS (ORDER BY observed_at RANGE BETWEEN INTERVAL '71 hours' PRECEDING AND CURRENT ROW);

-- Daily rainfall and wind summary, for dashboards and quick eyeballing.
CREATE OR REPLACE VIEW daily_weather AS
SELECT
    observed_at::date                        AS date,
    round(sum(precipitation_mm)::numeric, 2) AS rain_mm,
    round(max(precipitation_mm)::numeric, 2) AS peak_hourly_rain_mm,
    round(avg(temperature_c)::numeric, 1)    AS avg_temp_c,
    round(avg(wind_speed_kmh)::numeric, 1)   AS avg_wind_kmh,
    round(max(wind_gusts_kmh)::numeric, 1)   AS max_gust_kmh
FROM weather
GROUP BY observed_at::date;

-- Both turbidity eras in one long table: one row per reading per buoy,
-- missing readings dropped. phase says which cleanup era (and stretch of
-- canal) a row comes from. Station names are kept exactly as each era's
-- columns spell them, so RTA1 n_3sb and RTA2 n3sb stay separate: whether
-- they are the same instrument is unconfirmed (see README).
CREATE OR REPLACE VIEW turbidity AS
SELECT 'RTA1' AS phase, t.date + t.time AS measured_at, s.station, s.ntu,
       t.source_report
FROM turbidity_rta1 t
CROSS JOIN LATERAL (VALUES
    ('ambient', t.ambient), ('w_tb4', t.w_tb4), ('s_3sb', t.s_3sb),
    ('n_usb',   t.n_usb),   ('s_csb', t.s_csb), ('s_usb', t.s_usb),
    ('n_3sb',   t.n_3sb)
) AS s(station, ntu)
WHERE s.ntu IS NOT NULL
UNION ALL
SELECT 'RTA2', t.date + t.time, s.station, s.ntu, t.source_report
FROM turbidity_rta2 t
CROSS JOIN LATERAL (VALUES
    ('ambient', t.ambient), ('n3sb', t.n3sb), ('tb4', t.tb4)
) AS s(station, ntu)
WHERE s.ntu IS NOT NULL;

------------------------------------------------------------------------
-- Keep Supabase's public web API out. Supabase exposes the public schema
-- through a REST API to two built-in roles, anon (anyone holding the
-- project's public key) and authenticated, and grants them SELECT on
-- every new table and view. Row-level security already hides table rows
-- from them, but a view runs with its owner's rights and skips that --
-- so without this, duro_filtered handed the Dredgers' unpublished
-- readings to anyone with the key. Nothing in this project uses that API;
-- the loaders and the Streamlit app connect to Postgres directly.
-- Kept here, at the end, so every schema apply re-asserts it, including
-- for objects added above. The default-privileges line stops Supabase
-- granting these roles access to objects this login creates later.
------------------------------------------------------------------------
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
