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
-- NOAA tide predictions for station 8517921 (Gowanus Bay), from
-- tide_predictions.py.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tide_predictions (
    date                 date,
    time                 time,
    prediction_in_meters double precision,
    PRIMARY KEY (date, time)
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

CREATE TABLE IF NOT EXISTS weather (
    date         date,
    time         time,
    temperature  double precision,
    dew_point    double precision,
    humidity     double precision,
    wind         varchar,
    speed        double precision,
    gust         double precision,
    pressure     double precision,
    precip_rate  double precision,
    precip_accum double precision,
    uv           double precision,
    solar        double precision,
    PRIMARY KEY (date, time)
);

CREATE TABLE IF NOT EXISTS waterbody_advisories (
    id bigint PRIMARY KEY
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

-- Per-day, per-site summary for dashboards. Built on the filtered view so
-- out-of-water and unlocated readings never skew the stats.
CREATE OR REPLACE VIEW daily_site_summary AS
SELECT
    observed_at::date                     AS date,
    site,
    count(*)                              AS n_readings,
    round(avg(do_mg_l)::numeric, 2)       AS avg_do_mg_l,
    round(min(do_mg_l)::numeric, 2)       AS min_do_mg_l,
    round(max(do_mg_l)::numeric, 2)       AS max_do_mg_l,
    round(avg(water_temp_c)::numeric, 2)  AS avg_water_temp_c,
    round(avg(salinity_ppt)::numeric, 2)  AS avg_salinity_ppt,
    round(avg(ph)::numeric, 2)            AS avg_ph
FROM duro_filtered
GROUP BY observed_at::date, site;
