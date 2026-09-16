"""
Loads NOAA astronomical tide predictions into the `tide_predictions`
table in Supabase, one row per high or low tide.

Source: the NOAA CO-OPS API, which is public and needs no key. Station
8517921 is Gowanus Bay -- a *prediction* station, so these are predicted
heights above MLLW rather than measured water levels. If observed water
level ever matters (storm surge, for instance), the nearest station with
a real sensor is The Battery, 8518750.

    python tide_predictions.py                  # fill in whatever is missing
    python tide_predictions.py --dry-run        # fetch and summarize only
    python tide_predictions.py --start 2024-01-01 --end 2025-12-31
    python tide_predictions.py --full           # re-fetch everything

Predictions are astronomical, so they can be generated for future dates:
by default this loads from 2012 (the start of the CWQT bacteria record)
through one year ahead of today, and re-running simply refreshes them.
"""

import argparse
import datetime as dt

import pandas as pd
import requests

import apply_schema
import write_to_db

TABLE_NAME = 'tide_predictions'

API_URL = 'https://api.tidesandcurrents.noaa.gov/api/prod/datagetter'
STATION = '8517921'          # Gowanus Bay (predictions only)
EARLIEST = dt.date(2012, 1, 1)
YEARS_AHEAD = 1

FINAL_COLS = ['predicted_at', 'height_m', 'tide_type', 'station']


def fetch_year(begin: dt.date, end: dt.date) -> pd.DataFrame:
    """One request. NOAA limits a predictions range to about a year."""
    resp = requests.get(API_URL, params={
        'product': 'predictions',
        'application': 'gowanus_dredgers',
        'datum': 'MLLW',
        'station': STATION,
        'time_zone': 'lst_ldt',
        'units': 'metric',
        'interval': 'hilo',      # high/low events only, not 6-minute series
        'format': 'json',
        'begin_date': begin.strftime('%Y%m%d'),
        'end_date': end.strftime('%Y%m%d'),
    }, timeout=60)
    payload = resp.json()
    if 'error' in payload:
        raise RuntimeError(f"NOAA error for {begin}..{end}: "
                           f"{payload['error'].get('message', payload['error'])}")
    return pd.DataFrame(payload.get('predictions', []))


def get_data(start=None, end=None, full=False) -> pd.DataFrame:
    start = start or (EARLIEST if full else _resume_from())
    end = end or dt.date.today().replace(year=dt.date.today().year + YEARS_AHEAD)
    if start > end:
        print(f'  already current through {start - dt.timedelta(days=1)}')
        return pd.DataFrame(columns=FINAL_COLS)

    frames, cursor = [], start
    while cursor <= end:
        chunk_end = min(cursor.replace(year=cursor.year + 1) - dt.timedelta(days=1), end)
        print(f'  fetching {cursor} to {chunk_end}...')
        frames.append(fetch_year(cursor, chunk_end))
        cursor = chunk_end + dt.timedelta(days=1)

    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return pd.DataFrame(columns=FINAL_COLS)

    df = df.rename(columns={'t': 'predicted_at', 'v': 'height_m', 'type': 'tide_type'})
    df['predicted_at'] = pd.to_datetime(df['predicted_at'], errors='coerce')
    df['height_m'] = pd.to_numeric(df['height_m'], errors='coerce')
    df['station'] = STATION
    df = df.dropna(subset=['predicted_at'])
    df = df.drop_duplicates('predicted_at', keep='last').sort_values('predicted_at')
    return df.reindex(columns=FINAL_COLS)


def _resume_from() -> dt.date:
    """Refetch from the last stored day, so predictions stay refreshed."""
    from sqlalchemy import text
    with write_to_db.get_engine().connect() as conn:
        newest = conn.execute(
            text(f'SELECT max(predicted_at) FROM {TABLE_NAME}')).scalar()
    return EARLIEST if newest is None else newest.date()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='fetch and summarize without writing to the database')
    parser.add_argument('--start', type=dt.date.fromisoformat, default=None,
                        help='first date to fetch (YYYY-MM-DD)')
    parser.add_argument('--end', type=dt.date.fromisoformat, default=None,
                        help='last date to fetch (YYYY-MM-DD)')
    parser.add_argument('--full', action='store_true',
                        help='re-fetch the entire range, ignoring what is stored')
    args = parser.parse_args()

    print(f'Loading tide predictions for station {STATION}...')
    df = get_data(start=args.start, end=args.end, full=args.full)
    if df.empty:
        print('Nothing new to load.')
        return

    highs = df[df.tide_type == 'H']
    lows = df[df.tide_type == 'L']
    print(f'\n{len(df)} tide events, {df.predicted_at.min()} to {df.predicted_at.max()}')
    print(f'  highs: {len(highs)}, mean {highs.height_m.mean():.2f} m, '
          f'max {highs.height_m.max():.2f} m')
    print(f'  lows:  {len(lows)}, mean {lows.height_m.mean():.2f} m, '
          f'min {lows.height_m.min():.2f} m')

    if args.dry_run:
        print('\nDry run: nothing written to the database.')
        return

    apply_schema.apply()
    write_to_db.write_df_to_table(df, TABLE_NAME, pk_cols=['predicted_at'])


if __name__ == '__main__':
    main()
