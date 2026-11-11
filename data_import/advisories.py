"""
Loads the project lead's "Advisory Tracker" sheet into `waterbody_advisories`.

The tracker is a hand-kept log, from May 2024, of checks of NYC DEP's
waterbody advisory page for the two Gowanus areas DEP posts ("Gowanus Canal,
Inner" and "Outer"): whether each was under a wet-weather advisory, until
when, and notes. It is read as CSV, which needs the sheet shared as "Anyone
with the link: Viewer" (it is, as of 2026-11-11).

Usage:
    python advisories.py            # download and load
    python advisories.py --dry-run  # parse and summarise, write nothing

The table is replaced whole on every run, not upserted: the sheet is edited
by hand, rows have no stable key (the same check can appear twice, rows get
inserted), so the only reliable copy of it is a fresh one. sheet_row ties
each database row back to its line in the sheet.

Cleaning, so the messy hand entries become comparable:
- on_advisory: "Yes"/"YES"/"Yes " -> true; "No" and "NA" (the early entries'
  way of saying no advisory) -> false; blank -> NULL (not recorded).
- checked_at: DEP's "Server Date and Time" from the page, New York local
  time. advisory_until: the end time DEP gave, parsed out of the free text,
  only when it has AM/PM (a few entries were cut off).
- info_text keeps the raw "Advisory Info" text for anything not parsed.
- Rows with no area (blank lines, the footer) are dropped.
"""

import argparse
import io

import pandas as pd
import requests
from sqlalchemy import text

import apply_schema
import write_to_db

TABLE_NAME = 'waterbody_advisories'
SHEET_ID = '1ZLCwOtwXcmFWhdD3tQx-__P2GSzKSBtlUzUyZ54WXzs'   # "Advisory Tracker", first tab
CSV_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0'

COLUMNS = ['sheet_row', 'check_date', 'checked_at', 'area', 'on_advisory', 'advisory_until',
           'rain_gauge', 'emailed', 'info_text', 'notes', 'flushing_tunnel_status']


def download() -> pd.DataFrame:
    resp = requests.get(CSV_URL, timeout=60)
    resp.raise_for_status()
    if 'text/csv' not in resp.headers.get('content-type', ''):
        raise RuntimeError('The Advisory Tracker did not come back as CSV; is it still shared '
                           '"Anyone with the link: Viewer"?')
    return pd.read_csv(io.StringIO(resp.text), dtype=str, keep_default_na=False)


def _yes_no(s: pd.Series, no=('no', 'na')) -> pd.Series:
    v = s.str.strip().str.lower()
    return v.map(lambda x: True if x == 'yes' else False if x in no else None)


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df['sheet_row'] = df.index + 2                       # header is row 1
    df['area'] = df['Site'].str.strip().str.lower().str.extract(r'gowanus canal,\s*(inner|outer)')[0]
    df = df[df.area.notna()].copy()

    df['on_advisory'] = _yes_no(df['Advisory'])
    stamp = df['Time'].str.extract(r'Server Date and Time:\s*(\w{3} \d{1,2}, \d{4} \d{1,2}:\d{2}:\d{2} [AP]M)')[0]
    df['checked_at'] = pd.to_datetime(stamp, format='%b %d, %Y %I:%M:%S %p', errors='coerce')
    df['check_date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d', errors='coerce').dt.date
    df['check_date'] = df['check_date'].fillna(df['checked_at'].dt.date)

    info = df['Advisory Info'].str.strip()
    until = info.str.extract(r'(\d{1,2}/\d{1,2}/\d{4}, \d{1,2}:\d{2}(?::\d{2})? [AP]M)')[0]
    df['advisory_until'] = (pd.to_datetime(until, format='%m/%d/%Y, %I:%M:%S %p', errors='coerce')
                            .fillna(pd.to_datetime(until, format='%m/%d/%Y, %I:%M %p', errors='coerce')))
    df.loc[df.on_advisory != True, 'advisory_until'] = pd.NaT  # noqa: E712 ("has no advisory" texts)
    df['rain_gauge'] = info.str.extract(r'\b(RH)\s*$')[0]
    df['emailed'] = _yes_no(df['Email?'], no=('no',))
    df['info_text'] = info.replace('', None)
    df['notes'] = df['Notes'].str.strip().replace('', None)
    df['flushing_tunnel_status'] = df['Flushing Tunnel Status'].str.strip().replace('', None)
    df['checked_at'] = df['checked_at'].astype(object).where(df['checked_at'].notna(), None)
    df['advisory_until'] = df['advisory_until'].astype(object).where(df['advisory_until'].notna(), None)
    return df[COLUMNS].reset_index(drop=True)


def load(df: pd.DataFrame):
    with write_to_db.get_engine().begin() as conn:
        conn.execute(text(f'DELETE FROM {TABLE_NAME}'))
        df.to_sql(TABLE_NAME, conn, if_exists='append', index=False)
    print(f'{TABLE_NAME}: replaced with {len(df)} rows')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='parse and summarise without writing to the database')
    args = parser.parse_args()

    print('Downloading the Advisory Tracker...')
    df = clean(download())
    print(f'{len(df)} checks, {df.check_date.min()} to {df.check_date.max()}')
    print('On advisory:', df.on_advisory.value_counts(dropna=False).to_dict())
    print(f'{df.advisory_until.notna().sum()} advisories with an end time')
    if args.dry_run:
        print('\nDry run: nothing written to the database.')
        return
    apply_schema.apply()
    load(df)


if __name__ == '__main__':
    main()
