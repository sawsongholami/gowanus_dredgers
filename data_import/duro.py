"""
Loads raw Duro sonde CSVs into the `duro_readings` table in Supabase.

Usage:
    python duro.py            # parse every CSV in data/duro/ and upsert to the DB
    python duro.py --dry-run  # parse and print a summary, write nothing

Put the daily export CSVs (named MM-DD-YY.csv, one per outing) in data/duro/.
Re-running is safe: rows are upserted on their timestamp, so already-loaded
files are just refreshed, never duplicated.

The raw exports come in two known formats, both handled here:
  * Pre-Nov-2023: headers carry units ("RTD (ºC)", ...); every row has a value
    for all 17 columns, but the Altitude and Depth VALUES are swapped.
  * Post-Nov-2023: the sonde stopped recording Altitude but the header column
    remains, so each row has 16 values under 17 headers and everything from
    Depth onward is shifted left by one. Missing GPS is written as "------".
"""

import argparse
import csv
import pathlib as pl
import re

import numpy as np
import pandas as pd

import apply_schema
import sites
import write_to_db

DIR_THIS_DATA = pl.Path(__file__).parent.parent.absolute() / 'data' / 'duro'

TABLE_NAME = 'duro'

# Below this conductivity (µS/cm) the probe is assumed to be out of the water
# (the canal is brackish, typically 10,000+; per the data dictionary EC ~ 0
# means the probe is in air). Rows are flagged, never dropped.
OUT_OF_WATER_EC = 500

# Raw header -> canonical column name. Raw headers are matched after
# lowercasing and stripping units in parentheses, so both "RTD (ºC)" and
# "Water Temp" become water_temp_c.
HEADER_MAP = {
    'rtd': 'water_temp_c',
    'water temp': 'water_temp_c',
    'ph': 'ph',
    'orp': 'orp_mv',
    'ec': 'ec_us_cm',
    'tds': 'tds_ppm',
    'sal': 'salinity_ppt',
    'sg': 'specific_gravity',
    'do': 'do_mg_l',
    'sat': 'do_sat_pct',
    'pressure': 'pressure_mbar',
    'temperature': 'air_temp_c',
    'air temperature': 'air_temp_c',
    'altitude': 'altitude_m',
    'depth': 'depth_m',
    'time': 'time',
    'date': 'date',
    'latitude': 'latitude',
    'longitude': 'longitude',
}

NUMERIC_COLS = [
    'water_temp_c', 'ph', 'orp_mv', 'ec_us_cm', 'tds_ppm', 'salinity_ppt',
    'specific_gravity', 'do_mg_l', 'do_sat_pct', 'pressure_mbar',
    'air_temp_c', 'altitude_m', 'depth_m', 'latitude', 'longitude',
]

# Site bounding boxes (lat_min, lat_max, lon_min, lon_max), transcribed from
# the "Duro Data Dictionary" doc on the shared drive into db/sites.csv, the
# one list of sites. First match wins, in the CSV's order.
SITE_BOXES = sites.site_boxes()

MISSING_TOKENS = {'', '------'}

FINAL_COLS = [
    'observed_at', 'water_temp_c', 'ph', 'orp_mv', 'ec_us_cm', 'tds_ppm',
    'salinity_ppt', 'specific_gravity', 'do_mg_l', 'do_sat_pct',
    'pressure_mbar', 'air_temp_c', 'depth_m', 'latitude', 'longitude',
    'site', 'flag_out_of_water', 'source_file',
]


def _normalize_header(raw: str) -> str:
    name = re.sub(r'\(.*?\)', '', raw).strip().lower()
    return HEADER_MAP.get(name, name.replace(' ', '_'))


def parse_csv(path: pl.Path) -> pd.DataFrame:
    """Reads one raw export, absorbing the two known column layouts."""
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = [_normalize_header(h) for h in next(reader)]
        headers_shifted = [h for h in headers if h != 'altitude_m']

        records, skipped = [], 0
        for row in reader:
            row = [cell.strip() for cell in row]
            if not any(row):
                continue
            if len(row) == len(headers):
                records.append(dict(zip(headers, row)))
            elif len(row) == len(headers_shifted):
                # Altitude header present but value missing: shift names left.
                records.append(dict(zip(headers_shifted, row)))
            else:
                skipped += 1
    if skipped:
        print(f'  {path.name}: skipped {skipped} malformed row(s)')

    df = pd.DataFrame(records)
    df = df.mask(df.isin(MISSING_TOKENS))
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Pre-Nov-2023 files have the altitude and depth values swapped: depth
    # holds an impossible large negative number, altitude holds ~0.1 m.
    if 'altitude_m' in df.columns and 'depth_m' in df.columns:
        if df['depth_m'].median() < -20:
            df[['altitude_m', 'depth_m']] = df[['depth_m', 'altitude_m']].values
    df = df.drop(columns=['altitude_m'], errors='ignore')

    df['observed_at'] = pd.to_datetime(
        df['date'] + ' ' + df['time'], format='%m/%d/%Y %H:%M:%S', errors='coerce'
    )
    n_bad_ts = df['observed_at'].isna().sum()
    if n_bad_ts:
        print(f'  {path.name}: dropped {n_bad_ts} row(s) with unparseable timestamps')
    df = df.dropna(subset=['observed_at'])
    df = df.drop(columns=['date', 'time'])

    df['site'] = assign_sites(df['latitude'], df['longitude'])
    df['flag_out_of_water'] = df['ec_us_cm'] < OUT_OF_WATER_EC
    df['source_file'] = path.name
    return df


def assign_sites(lat: pd.Series, lon: pd.Series) -> pd.Series:
    """Maps GPS coordinates to named sites via the data dictionary's boxes."""
    site = pd.Series(np.nan, index=lat.index, dtype=object)
    has_gps = lat.notna() & lon.notna()
    site[has_gps] = 'TBD'
    for name, lat_min, lat_max, lon_min, lon_max in SITE_BOXES:
        in_box = (
            has_gps & (site == 'TBD')
            & lat.between(lat_min, lat_max) & lon.between(lon_min, lon_max)
        )
        site[in_box] = name
    return site


def get_data() -> pd.DataFrame:
    csv_paths = sorted(DIR_THIS_DATA.glob('*.csv'))
    if not csv_paths:
        raise FileNotFoundError(f'No CSVs found in {DIR_THIS_DATA}')

    frames = []
    for path in csv_paths:
        df = parse_csv(path)
        print(f'  {path.name}: {len(df)} rows')
        frames.append(df)

    df = pd.concat(frames, ignore_index=True)
    # The same timestamp can appear in overlapping exports; keep the last.
    df = df.sort_values('observed_at').drop_duplicates('observed_at', keep='last')
    return df[FINAL_COLS]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='parse and summarize without writing to the database')
    args = parser.parse_args()

    print(f'Reading raw Duro CSVs from {DIR_THIS_DATA}')
    df = get_data()

    print(f'\nTotal: {len(df)} readings, '
          f'{df.observed_at.min()} to {df.observed_at.max()}')
    print(f'Out-of-water flagged: {df.flag_out_of_water.sum()}')
    print('Site counts (NaN = no GPS fix):')
    print(df.site.value_counts(dropna=False).to_string())

    if args.dry_run:
        print('\nDry run: nothing written to the database.')
        return

    apply_schema.apply()
    write_to_db.write_df_to_table(df, TABLE_NAME, pk_cols=['observed_at'])


if __name__ == '__main__':
    main()
