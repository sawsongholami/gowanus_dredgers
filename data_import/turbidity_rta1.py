"""
Loads RTA1-era turbidity data into the `turbidity_rta1` table in Supabase
from local exports of the GRT spreadsheets on the shared drive.

The RTA1 weekly Water Quality Monitoring reports embed their data tables
as images, so they cannot be scraped; these spreadsheets are the only
machine-readable form of that era. Two files are read from
data/turbidity_rta1/:

  GRT_Reports.xlsx   PRIMARY. A transcription of the RTA1 weekly report
                     PDFs: one row per 15-minute reading, one column per
                     monitoring buoy, naming the source PDF per row.
                     Covers Aug 2023 - Apr 2024 during report hours, but
                     has a gap with no rows at all from Feb 4 to Mar 30,
                     2024.

  together_data.xlsx GAP FILL ONLY. Round-the-clock 15-minute readings
                     that cover that Feb-Mar 2024 gap. Its `ambient` and
                     `w_tb4` columns match GRT_Reports exactly on every
                     shared timestamp (verified: 14,396 and 14,081 values,
                     zero differences), so they load with confidence.
                     Its other two columns (`s_csb`, `s3sb`) are NOT
                     single stations -- each matches a different GRT
                     column in different periods, because the buoys were
                     physically relocated during the project. They are
                     therefore left NULL rather than guessed at; the file
                     stays in the repo so the values can be recovered if
                     someone confirms the buoy deployment schedule with
                     GRT.

To refresh either file: open it on the shared drive (Other_Water_Data/),
File > Download > Microsoft Excel (.xlsx), and save it into
data/turbidity_rta1/ under the same name. Usage:

    python turbidity_rta1.py            # parse and upsert
    python turbidity_rta1.py --dry-run  # parse and summarize, write nothing
"""

import argparse
import pathlib as pl

import pandas as pd

import apply_schema
import write_to_db

TABLE_NAME = 'turbidity_rta1'

DIR_THIS_DATA = pl.Path(__file__).parent.parent.absolute() / 'data' / 'turbidity_rta1'
PRIMARY_FILE = 'GRT_Reports.xlsx'
GAPFILL_FILE = 'together_data.xlsx'

# GRT_Reports.xlsx column -> database column.
PRIMARY_COLUMN_MAP = {
    'Report': 'source_report',
    'Date': 'date',
    'Time': 'time',
    'Ambient': 'ambient',
    'W_TB4': 'w_tb4',
    'S_3SB': 's_3sb',
    'N_USB': 'n_usb',
    'S_CSB': 's_csb',
    'S_USB': 's_usb',
    'N_3SB': 'n_3sb',
}

# together_data.xlsx column -> database column. Only the two columns that
# were verified identical to GRT_Reports on shared timestamps; see the
# module docstring for why s_csb / s3sb are deliberately excluded.
GAPFILL_COLUMN_MAP = {
    'ambient': 'ambient',
    'w_tb4': 'w_tb4',
}

STATION_COLS = ['ambient', 'w_tb4', 's_3sb', 'n_usb', 's_csb', 's_usb', 'n_3sb']
FINAL_COLS = ['date', 'time', *STATION_COLS, 'source_report']


def _read(name: str) -> pd.DataFrame:
    path = DIR_THIS_DATA / name
    if not path.exists():
        raise FileNotFoundError(
            f'{name} not found in {DIR_THIS_DATA}. Download it from the '
            'shared drive (File > Download > .xlsx) and save it there; '
            'see the note at the top of this script.'
        )
    return pd.read_excel(path)


def get_primary() -> pd.DataFrame:
    df = _read(PRIMARY_FILE).rename(columns=PRIMARY_COLUMN_MAP)
    df = df.loc[:, [c for c in FINAL_COLS if c in df.columns]]
    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
    df['time'] = pd.to_datetime(df['time'].astype(str), format='mixed',
                                errors='coerce').dt.time
    # Missing readings are written as '‐‐' (unicode hyphens) or '--'.
    for col in STATION_COLS:
        df[col] = pd.to_numeric(df.get(col), errors='coerce')
    return df.dropna(subset=['date', 'time'])


def get_gapfill() -> pd.DataFrame:
    df = _read(GAPFILL_FILE).rename(columns=GAPFILL_COLUMN_MAP)
    ts = pd.to_datetime(df['datetime_cl'], errors='coerce')
    if getattr(ts.dt, 'tz', None) is not None:
        ts = ts.dt.tz_localize(None)
    df['date'], df['time'] = ts.dt.date, ts.dt.time
    for col in STATION_COLS:
        # Untrusted stations are float-typed NaN, not pd.NA, so concat with
        # the primary frame keeps a single numeric dtype per column.
        df[col] = (pd.to_numeric(df[col], errors='coerce')
                   if col in GAPFILL_COLUMN_MAP.values()
                   else pd.Series(float('nan'), index=df.index, dtype='float64'))
    df['source_report'] = GAPFILL_FILE
    df = df.dropna(subset=['date', 'time'])
    # Keep only rows that actually carry one of the two trusted readings.
    return df[df[list(GAPFILL_COLUMN_MAP.values())].notna().any(axis=1)]


def get_data() -> pd.DataFrame:
    primary = get_primary()
    gapfill = get_gapfill()
    print(f'  {PRIMARY_FILE}: {len(primary)} readings')
    print(f'  {GAPFILL_FILE}: {len(gapfill)} readings with trusted values')

    # Primary first so it wins the dedupe wherever both cover a timestamp.
    df = pd.concat([primary, gapfill], ignore_index=True)
    before = len(df)
    df = df.drop_duplicates(['date', 'time'], keep='first')
    print(f'  {before - len(df)} rows dropped as duplicate timestamps')
    return df.reindex(columns=FINAL_COLS).sort_values(['date', 'time'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='parse and summarize without writing to the database')
    args = parser.parse_args()

    print('Reading local GRT exports...')
    df = get_data()
    print(f'\nTotal: {len(df)} readings, {df.date.min()} to {df.date.max()}')
    print('non-null readings per station:')
    print(df[STATION_COLS].notna().sum().to_string())
    print('rows by source:')
    print(df.source_report.map(
        lambda r: GAPFILL_FILE if r == GAPFILL_FILE else PRIMARY_FILE
    ).value_counts().to_string())

    if args.dry_run:
        print('\nDry run: nothing written to the database.')
        return

    apply_schema.apply()
    write_to_db.write_df_to_table(df, TABLE_NAME, pk_cols=['date', 'time'])


if __name__ == '__main__':
    main()
