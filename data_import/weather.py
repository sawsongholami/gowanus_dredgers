"""
Loads hourly weather for the Gowanus Canal into the `weather` table in
Supabase, from the Open-Meteo historical API (ERA5 reanalysis).

Open-Meteo needs no API key and is free for non-commercial use, which is
why it was chosen: there is no credential for a volunteer maintainer to
rotate or leak. Attribution is required if this data is published --
"Weather data by Open-Meteo.com" (CC BY 4.0).

    python weather.py                          # backfill everything missing
    python weather.py --dry-run                # parse and summarize only
    python weather.py --start 2024-01-01       # explicit window
    python weather.py --full                   # re-fetch the whole history

By default the script only fetches from the day after the newest row
already stored, so routine runs pull a few days and a first run pulls the
whole history (about 129,000 hours, one request, a few seconds).

CAVEAT worth repeating to anyone using the numbers: ERA5 is a modelled
reanalysis on a ~9-25 km grid, not a rain gauge in Gowanus. It is good
for correlating rainfall against water quality, but a localised summer
thunderstorm -- exactly the kind that triggers a CSO -- can be smoothed
out. If gauge-accurate local rainfall ever matters more than convenience,
NOAA NCEI's Central Park record is the alternative (and is the same gauge
the CWQT program uses for its own precipitation columns).
"""

import argparse
import datetime as dt

import pandas as pd
import requests

import apply_schema
import write_to_db

TABLE_NAME = 'weather'

API_URL = 'https://archive-api.open-meteo.com/v1/archive'
LATITUDE, LONGITUDE = 40.675, -73.990   # mid-canal, near Third Street
TIMEZONE = 'America/New_York'

# Earliest date worth fetching: the CWQT bacteria record starts May 2012,
# and rainfall is the main thing we want to correlate against it.
EARLIEST = dt.date(2012, 1, 1)

# Open-Meteo hourly variable -> database column.
VARIABLES = {
    'temperature_2m': 'temperature_c',
    'dew_point_2m': 'dew_point_c',
    'relative_humidity_2m': 'humidity_pct',
    'precipitation': 'precipitation_mm',
    'rain': 'rain_mm',
    'wind_speed_10m': 'wind_speed_kmh',
    'wind_direction_10m': 'wind_direction_deg',
    'wind_gusts_10m': 'wind_gusts_kmh',
    'surface_pressure': 'pressure_hpa',
    'shortwave_radiation': 'solar_wm2',
}

FINAL_COLS = ['observed_at', *VARIABLES.values()]


def latest_stored():
    """Newest observed_at already in the table, or None if it is empty."""
    from sqlalchemy import text
    with write_to_db.get_engine().connect() as conn:
        row = conn.execute(
            text(f'SELECT max(observed_at) FROM {TABLE_NAME}')).scalar()
    return row.date() if row else None


def fetch(start: dt.date, end: dt.date) -> pd.DataFrame:
    resp = requests.get(API_URL, params={
        'latitude': LATITUDE,
        'longitude': LONGITUDE,
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
        'hourly': ','.join(VARIABLES),
        'timezone': TIMEZONE,
    }, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(
            f'Open-Meteo returned {resp.status_code}: {resp.text[:200]}')

    hourly = resp.json()['hourly']
    df = pd.DataFrame(hourly).rename(columns=VARIABLES)
    df['observed_at'] = pd.to_datetime(df.pop('time'))
    # The most recent day or two can come back with empty placeholder rows.
    value_cols = list(VARIABLES.values())
    df = df.dropna(subset=value_cols, how='all')
    return df.reindex(columns=FINAL_COLS).sort_values('observed_at')


def get_data(start=None, end=None, full=False) -> pd.DataFrame:
    end = end or dt.date.today()
    if start is None:
        last = None if full else latest_stored()
        start = EARLIEST if last is None else last + dt.timedelta(days=1)
    if start > end:
        print(f'  already current through {start - dt.timedelta(days=1)}')
        return pd.DataFrame(columns=FINAL_COLS)

    print(f'  fetching {start} to {end} from Open-Meteo...')
    return fetch(start, end)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='fetch and summarize without writing to the database')
    parser.add_argument('--start', type=dt.date.fromisoformat, default=None,
                        help='first date to fetch (YYYY-MM-DD)')
    parser.add_argument('--end', type=dt.date.fromisoformat, default=None,
                        help='last date to fetch (YYYY-MM-DD); defaults to today')
    parser.add_argument('--full', action='store_true',
                        help='re-fetch the entire history, ignoring what is stored')
    args = parser.parse_args()

    print('Loading hourly weather from Open-Meteo...')
    df = get_data(start=args.start, end=args.end, full=args.full)
    if df.empty:
        print('Nothing new to load.')
        return

    rain_days = df.set_index('observed_at').precipitation_mm.resample('D').sum()
    print(f'\n{len(df)} hours, {df.observed_at.min()} to {df.observed_at.max()}')
    print(f'  total precipitation: {df.precipitation_mm.sum():.0f} mm '
          f'over {len(rain_days)} days ({int((rain_days > 0.1).sum())} with rain)')
    print(f'  wind: mean {df.wind_speed_kmh.mean():.1f} km/h, '
          f'peak gust {df.wind_gusts_kmh.max():.1f} km/h')

    if args.dry_run:
        print('\nDry run: nothing written to the database.')
        return

    apply_schema.apply()
    write_to_db.write_df_to_table(df, TABLE_NAME, pk_cols=['observed_at'])


if __name__ == '__main__':
    main()
