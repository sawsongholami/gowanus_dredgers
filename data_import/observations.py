"""
Loads Gowanus Observation Survey responses (Google Form) into the
`observations` table in Supabase.

Usage:
    python observations.py            # download responses and upsert
    python observations.py --dry-run  # parse and summarize, write nothing

The form writes into its linked response spreadsheet; this script downloads
that sheet as CSV. For the download to work without any Google credentials,
the response spreadsheet must be shared as "Anyone with the link: Viewer"
(Share button in the sheet, top right). Re-running is safe: rows are
upserted on (submitted_at, observer_id).
"""

import argparse
import io

import numpy as np
import pandas as pd
import requests

import apply_schema
import duro
import write_to_db

TABLE_NAME = 'observations'

RESPONSES_SHEET_ID = '1NsOlTt3dsqUlue2nb-4giEajafBk_dO7Gco0ixRjf8M'
CSV_URL = (f'https://docs.google.com/spreadsheets/d/{RESPONSES_SHEET_ID}'
           '/export?format=csv')

# Response-sheet column header -> database column. If a question's wording
# is edited in the Forms editor, its sheet header changes too and must be
# updated here.
COLUMN_MAP = {
    'Timestamp': 'submitted_at',
    'Observer ID': 'observer_id',
    'Where are you?': 'location',
    'If somewhere else: latitude': 'latitude',
    'If somewhere else: longitude': 'longitude',
    "Today's date": 'observed_date',
    'Time of observation': 'observed_time',
    'Do you see any litter in the water of the canal?': 'litter',
    'Do you see any dead organisms?': 'dead_organisms',
    'Do you see any living organisms?': 'living_organisms',
    'Which words best describe what the water in the canal looks like?':
        'water_appearance',
    'Do you see any oil sheen on the water?': 'oil_sheen',
    'What can you smell?': 'smells',
    'What can you hear?': 'sounds',
    'Is there anything else you want to record?': 'notes',
}

# Form dropdown choice -> canonical site slug (the same slugs duro.py
# assigns from GPS bounding boxes, so the two tables can be joined on site).
# Union_St has no Duro bounding box yet; it simply won't join.
LOCATION_TO_SITE = {
    'Douglass Street': 'Douglass_St',
    'Carroll Street Bridge': 'Carroll_St',
    'Union Street Bridge': 'Union_St',
    'Boathouse at 2nd Street': 'Second_St',
    '3rd Street Bridge': 'Third_St',
    '9th Street Bridge': 'Ninth_St_Bridge',
    'Bunker at 19th Street': 'GD_Bunker',
}

SOMEWHERE_ELSE = 'Somewhere else (enter coordinates below)'

FINAL_COLS = [
    'submitted_at', 'observer_id', 'location', 'site', 'latitude',
    'longitude', 'observed_date', 'observed_time', 'litter',
    'dead_organisms', 'living_organisms', 'water_appearance', 'oil_sheen',
    'smells', 'sounds', 'notes',
]


def download_responses() -> pd.DataFrame:
    resp = requests.get(CSV_URL)
    is_html = resp.content[:100].lstrip().lower().startswith(b'<')
    if resp.status_code != 200 or is_html:
        raise RuntimeError(
            'Could not download the response spreadsheet. Open it in Google '
            'Sheets and set sharing to "Anyone with the link: Viewer", then '
            f'try again. ({CSV_URL})'
        )
    return pd.read_csv(io.BytesIO(resp.content))


def clean(df: pd.DataFrame) -> pd.DataFrame:
    unknown = [c for c in df.columns if c not in COLUMN_MAP]
    if unknown:
        print(f'  Ignoring unrecognized sheet columns: {unknown}\n'
              '  (a form question was probably added or reworded; '
              'update COLUMN_MAP in observations.py)')
    df = df.rename(columns=COLUMN_MAP)
    df = df.loc[:, [c for c in FINAL_COLS if c in df.columns]]

    df['submitted_at'] = pd.to_datetime(df['submitted_at'], errors='coerce')
    df = df.dropna(subset=['submitted_at'])

    # Sheets stores the 4-digit ID as a number, which eats leading zeros.
    df['observer_id'] = (df['observer_id'].astype('Int64').astype(str)
                         .str.zfill(4).replace('<NA>', np.nan))

    df['observed_date'] = pd.to_datetime(df['observed_date'],
                                         errors='coerce').dt.date
    df['observed_time'] = pd.to_datetime(df['observed_time'], format='mixed',
                                         errors='coerce').dt.time
    for col in ('latitude', 'longitude'):
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Canonical site: named locations map directly; "somewhere else" rows
    # get a site from their coordinates via the Duro bounding boxes.
    df['site'] = df['location'].map(LOCATION_TO_SITE)
    somewhere = df['location'] == SOMEWHERE_ELSE
    if somewhere.any():
        df.loc[somewhere, 'site'] = duro.assign_sites(
            df.loc[somewhere, 'latitude'], df.loc[somewhere, 'longitude'])
    df.loc[somewhere, 'location'] = np.nan

    df = df.sort_values('submitted_at').drop_duplicates(
        ['submitted_at', 'observer_id'], keep='last')
    return df.reindex(columns=FINAL_COLS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='parse and summarize without writing to the database')
    args = parser.parse_args()

    print('Downloading survey responses...')
    df = clean(download_responses())

    if df.empty:
        print('No responses in the sheet yet; nothing to load.')
        return

    print(f'{len(df)} responses, {df.submitted_at.min()} to {df.submitted_at.max()}')
    print('Site counts:')
    print(df.site.value_counts(dropna=False).to_string())

    if args.dry_run:
        print('\nDry run: nothing written to the database.')
        return

    apply_schema.apply()
    write_to_db.write_df_to_table(df, TABLE_NAME,
                                  pk_cols=['submitted_at', 'observer_id'])


if __name__ == '__main__':
    main()
