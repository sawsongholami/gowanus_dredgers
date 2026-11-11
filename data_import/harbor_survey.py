"""
Loads NYC DEP's Harbor Survey samples for the Gowanus Canal into
`harbor_survey`, from NYC Open Data ("Harbor Water Quality", 5uug-f49n).

The Harbor Survey is DEP's own long-running boat survey, separate from
CWQT: oxygen, temperature, salinity, clarity and bacteria at fixed stations,
with canal records back to 1909. The canal stations, head to mouth:
GC3 (Butler St), GC4 (Carroll St), GC5 (3rd St), GC6 (9th St), G2 (the
mouth); plus a handful of one-off 2000-2003 stations (GC, GC2, GC2a, GC-HAB,
GC-mouth). GB1, "Gowanus Bay", is out in the bay off Bay Ridge, so it is left
out.

Usage:
    python harbor_survey.py            # download and upsert
    python harbor_survey.py --dry-run  # parse and summarise, write nothing

Rows are upserted on obs_id, the dataset's own row id, so re-runs are safe.
Cleaning:
- bacteria counts arrive as text with thousands separators ("1,000") and
  occasional qualifiers ("<10", ">2,400"); stored as the number, as cwqt
  does. Codes with no number ("QD") become NULL.
- weather: "D"/"Dry"/"DRY" -> 'dry', "W"/"Wet"/"WET" -> 'wet'.
- the dataset's `lat` and `long` columns are swapped on many rows; each row
  is put right by which value looks like a latitude.
- of the oxygen readings, both the CTD profiler and the Winkler titration
  are kept (different methods; the CTD runs from 2014ish).
"""

import argparse
import io

import numpy as np
import pandas as pd

import apply_schema
import web
import write_to_db

TABLE_NAME = 'harbor_survey'
URL = 'https://data.cityofnewyork.us/resource/5uug-f49n.csv'
WHERE = "starts_with(sampling_location,'GC') or sampling_location='G2'"

# Source column -> database column (the source names run past Postgres's
# 63-character limit).
COLUMN_MAP = {
    ':id': 'obs_id',
    'sampling_location': 'station',
    'sample_date': 'sample_date',
    'sample_time': 'sample_time',
    'weather_condition_dry_or_wet': 'weather',
    'site_actual_depth_ft': 'site_depth_ft',
    'top_sample_temperature_c': 'top_temp_c',
    'bottom_sample_temperature_c': 'bottom_temp_c',
    'top_salinity_psu': 'top_salinity_psu',
    'bottom_salinity_psu': 'bottom_salinity_psu',
    'ctd_conductivity_temperature_depth_profiler_top_dissolved_oxygen_mg_l': 'top_do_ctd_mg_l',
    'ctd_conductivity_temperature_depth_profiler_bottom_dissolved_oxygen_mg_l': 'bottom_do_ctd_mg_l',
    'winkler_method_top_dissolved_oxygen_mg_l': 'top_do_winkler_mg_l',
    'winkler_method_bottom_dissolved_oxygen_mg_l': 'bottom_do_winkler_mg_l',
    'percentage_o2_saturation_top_sample': 'top_do_sat_pct',
    'percentage_o2_saturation_bottom_sample': 'bottom_do_sat_pct',
    'secchi_depth_ft': 'secchi_depth_ft',
    'top_ph': 'top_ph',
    'bottom_ph': 'bottom_ph',
    'top_enterococci_bacteria_cells_100ml': 'top_enterococci',
    'bottom_enterococci_bacteria_cells_100ml': 'bottom_enterococci',
    'top_fecal_coliform_bacteria_cells_100ml': 'top_fecal_coliform',
    'bottom_fecal_coliform_bacteria_cells_100ml': 'bottom_fecal_coliform',
    'top_total_suspended_solid_mg_l': 'top_tss_mg_l',
    'bottom_total_suspended_solid_mg_l': 'bottom_tss_mg_l',
    'top_active_chlorophyll_a_g_l': 'top_chlorophyll_a_ug_l',
    'lat': 'lat',
    'long': 'lon',
}
TEXT_COLS = {'obs_id', 'station', 'sample_date', 'sample_time', 'weather'}


def download() -> pd.DataFrame:
    params = {'$select': ','.join(COLUMN_MAP), '$where': WHERE, '$limit': 100000}
    resp = web.get(URL, params=params, timeout=120)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text), dtype=str)


def _number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.replace(r'[,<>\s]', '', regex=True), errors='coerce')


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=COLUMN_MAP)[list(COLUMN_MAP.values())].copy()
    for col in set(df.columns) - TEXT_COLS:
        df[col] = _number(df[col])
    # Put swapped coordinates right: a latitude here is about 40.7, a longitude about -74.
    swapped = df.lat < 0
    df.loc[swapped, ['lat', 'lon']] = df.loc[swapped, ['lon', 'lat']].values
    df.loc[~df.lat.between(40, 41.5) | (df.lat == 41), ['lat', 'lon']] = np.nan   # 41/-74 placeholders
    df['sample_date'] = pd.to_datetime(df.sample_date).dt.date
    t = pd.to_datetime(df.sample_time.str.strip(), format='%H:%M', errors='coerce')
    t = t.fillna(pd.to_datetime(df.sample_time.str.strip(), format='%I:%M %p', errors='coerce'))
    df['sample_time'] = t.dt.time.where(t.notna(), None)
    df['weather'] = (df.weather.str.strip().str.lower().str[0]
                     .map({'d': 'dry', 'w': 'wet'}).where(df.weather.notna(), None))
    return df.astype(object).where(df.notna(), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='parse and summarise without writing to the database')
    args = parser.parse_args()

    print('Downloading Harbor Survey canal samples...')
    df = clean(download())
    print(f'{len(df)} samples, {min(df.sample_date)} to {max(df.sample_date)}')
    print(df.station.value_counts().to_string())
    if args.dry_run:
        print('\nDry run: nothing written to the database.')
        return
    apply_schema.apply()
    write_to_db.write_df_to_table(df, TABLE_NAME, pk_cols=['obs_id'])


if __name__ == '__main__':
    main()
