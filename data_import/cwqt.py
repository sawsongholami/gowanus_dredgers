"""
Loads CWQT Enterococcus sampling for the Gowanus sites into the `cwqt`
table in Supabase, combining two sources at load time:

  1. The citywide CWQT Master Data Sheet (SwimmableNYC / Billion Oyster
     Project), "Data" tab, filtered to the two Gowanus sites. Live and
     maintained by the program: regular seasons (May-Oct) 2012-present.
  2. The "Enterococcus at 2nd St" sheet: winter 2023-24 off-season
     sampling at Second Street, processed by the NY Harbor School.
     This data does not exist in the master sheet.

Where both sources have a row for the same date+site, the master wins.
Both sheets are public ("anyone with the link"), so no credentials are
needed. Usage:

    python cwqt.py            # download both sources and upsert
    python cwqt.py --dry-run  # parse and summarize, write nothing
"""

import argparse
import io

import numpy as np
import pandas as pd
import requests

import apply_schema
import write_to_db

TABLE_NAME = 'cwqt'

MASTER_SHEET_ID = '1813b2nagaxZ80xRfyMZNNKySZOitro5Nt7W4E9WNQDA'
WINTER_SHEET_ID = '1GA7MZmNzw-TCv0tZ8T6F_r0HxFuZdAmenaWXUCpxmgA'

# Program site name -> canonical slug. Slugs join against duro.site where
# a Duro bounding box exists; Lowlands and Dentons_Pond stand alone.
# site_id comes from the master sheet's own Site ID column.
SITES = {
    'Gowanus Canal, Second Street Sponge Park': 'Second_St',
    'Gowanus Canal, Lowlands Nursery': 'Lowlands',
    'Gowanus Canal, 2nd Avenue Salt Lot': 'Second_Ave',
    'Gowanus Canal, Bond Street': 'Bond_St',
    'Gowanus Canal, Carroll Street': 'Carroll_St',
    "Gowanus Canal, Denton's Pond Outfall": 'Dentons_Pond',
}

# For sources that lack a Site ID column (the winter sheet).
NAME_TO_ID = {'Gowanus Canal, Second Street Sponge Park': 23}

MASTER_COLUMN_MAP = {
    'Site': 'site_name',
    'Site ID': 'site_id',
    'Full Date': 'date',
    'Battery High Tide': 'battery_high_tide',
    'Sample Time': 'sample_time',
    'Most Probable Number (MPN) of Enterococcus colonies per 100 ml': 'mpn_raw',
    'Day of Collection Precipitation (Thursday)': 'precip_on_collection_day',
    'Previous Day Precipitation (Wednesday)': 'precip_1_day_before_collection',
    'Previous Tuesday Precipitation': 'precip_2_days_before_collection',
    'Previous Monday Precipitation': 'precip_3_days_before_collection',
    'Previous Sunday Precipitation': 'precip_4_days_before_collection',
    'Previous Saturday Precipitation': 'precip_5_days_before_collection',
    'Previous Friday Precipitation': 'precip_6_days_before_collection',
    'Notes': 'notes',
}

PRECIP_COLS = [c for c in MASTER_COLUMN_MAP.values() if c.startswith('precip')]

FINAL_COLS = [
    'date', 'site_id', 'site', 'site_name', 'sample_time', 'mpn', 'mpn_raw',
    'battery_high_tide', *PRECIP_COLS, 'notes', 'source',
]


def _download(url: str, what: str) -> bytes:
    resp = requests.get(url)
    if resp.status_code != 200 or resp.content[:100].lstrip().lower().startswith(b'<'):
        raise RuntimeError(
            f'Could not download {what}. The sheet must be shared as '
            f'"Anyone with the link: Viewer". ({url})'
        )
    return resp.content


def _parse_mpn(raw: pd.Series) -> pd.Series:
    """'<10' -> 10, '>24196' -> 24196, 'Lab error'/'N/A' -> NaN."""
    cleaned = (raw.astype(str).str.strip()
               .str.replace(r'^[<>]\s*', '', regex=True)
               .str.replace(',', ''))
    return pd.to_numeric(cleaned, errors='coerce')


def _to_time(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), format='mixed',
                          errors='coerce').dt.time


def get_master() -> pd.DataFrame:
    url = (f'https://docs.google.com/spreadsheets/d/{MASTER_SHEET_ID}'
           '/export?format=xlsx')
    raw = pd.read_excel(io.BytesIO(_download(url, 'the CWQT Master Data Sheet')),
                        sheet_name='Data')
    df = raw[raw['Site'].isin(SITES)].rename(columns=MASTER_COLUMN_MAP)

    df['mpn_raw'] = df['mpn_raw'].astype(str).str.strip()
    df['mpn'] = _parse_mpn(df['mpn_raw'])
    for col in PRECIP_COLS:
        # 'Trace' means measurable-but-tiny; recorded as 0 per schema.sql.
        df[col] = pd.to_numeric(
            df[col].replace('Trace', 0), errors='coerce')
    for col in ('sample_time', 'battery_high_tide'):
        df[col] = _to_time(df[col])
    df['source'] = 'cwqt_master'
    return df


def get_winter() -> pd.DataFrame:
    url = (f'https://docs.google.com/spreadsheets/d/{WINTER_SHEET_ID}'
           '/export?format=csv')
    raw = pd.read_csv(io.BytesIO(_download(url, 'the Enterococcus at 2nd St sheet')))

    df = raw[raw['SamplingSite'].isin(SITES)].rename(columns={
        'SamplingSite': 'site_name',
        'Date': 'date',
        'Sample Time': 'sample_time',
        'MPN': 'mpn_raw',
        'Notes': 'notes',
    })
    df['mpn_raw'] = df['mpn_raw'].astype(str).str.strip()
    df['mpn'] = _parse_mpn(df['mpn_raw'])
    df['sample_time'] = _to_time(df['sample_time'])
    df['source'] = 'winter_2nd_st'
    return df


def get_data() -> pd.DataFrame:
    master = get_master()
    winter = get_winter()
    print(f'  master sheet: {len(master)} Gowanus rows')
    print(f'  winter sheet: {len(winter)} rows')

    # Master first so it wins the dedupe on overlapping date+site.
    df = pd.concat([master, winter], ignore_index=True)
    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
    df = df.dropna(subset=['date'])
    df['site'] = df['site_name'].map(SITES)
    df['site_id'] = (pd.to_numeric(df.get('site_id'), errors='coerce')
                     .fillna(df['site_name'].map(NAME_TO_ID)).astype(int))
    df['mpn_raw'] = df['mpn_raw'].replace({'nan': np.nan})
    df = df.drop_duplicates(['date', 'site_id'], keep='first')
    return df.reindex(columns=FINAL_COLS).sort_values(['date', 'site_id'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='parse and summarize without writing to the database')
    args = parser.parse_args()

    print('Downloading CWQT sources...')
    df = get_data()

    print(f'\nTotal: {len(df)} samples, {df.date.min()} to {df.date.max()}')
    print(df.groupby(['site', 'source']).size().to_string())
    print(f'MPN present: {df.mpn.notna().sum()}, censored/non-numeric raw: '
          f'{(df.mpn_raw.notna() & df.mpn.isna()).sum()}')

    if args.dry_run:
        print('\nDry run: nothing written to the database.')
        return

    apply_schema.apply()
    write_to_db.write_df_to_table(df, TABLE_NAME, pk_cols=['date', 'site_id'])


if __name__ == '__main__':
    main()
