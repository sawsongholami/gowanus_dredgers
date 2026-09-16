"""
Loads RTA2-era turbidity data into the `turbidity_rta2` table in Supabase
by scraping the weekly Water Quality Monitoring reports (PDFs) posted at
https://gowanussuperfund.com/monitoring-data/.

Each weekly report carries an Appendix A with one 15-minute turbidity
table per workday (stations: Ambient, N3SB, TB4). This script:

  1. fetches the monitoring page and finds every RTA2 weekly-report URL
     (no hardcoded filenames or upload dates);
  2. downloads any PDFs not already cached in data/turbidity_rta2/;
  3. parses every appendix table in every report;
  4. upserts on (date, time).

Usage:
    python turbidity_rta2.py             # scrape everything new + load
    python turbidity_rta2.py --dry-run   # parse only, write nothing
    python turbidity_rta2.py --limit 3   # only the 3 newest reports

The RTA1-era reports (2020 - early 2024) embed their tables as images and
cannot be text-scraped; that era loads from a CSV export of the
GRT_Reports Google Sheet instead (see turbidity_rta1.py).
"""

import argparse
import pathlib as pl
import re

import pandas as pd
import pdfplumber
import requests

import apply_schema
import write_to_db

TABLE_NAME = 'turbidity_rta2'

MONITORING_URL = 'https://gowanussuperfund.com/monitoring-data/'
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/137.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://gowanussuperfund.com/',
}

# Matches the RTA2 weekly-report family, including early naming quirks
# (RTA-2-..., _Week-008_.pdf, _001.pdf).
REPORT_URL_RE = re.compile(
    r'href="(https?://[^"]*RTA-?2-WQM-Weekly-Report[^"]*\.pdf)"'
)

DIR_PDF = pl.Path(__file__).parent.parent.absolute() / 'data' / 'turbidity_rta2'

# Station name (as printed in the table header) -> database column.
STATIONS = {'ambient': 'ambient', 'n3sb': 'n3sb', 'tb4': 'tb4'}

DATE_RE = re.compile(r'^\d{1,2}/\d{1,2}/\d{2,4}$')
TIME_RE = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$')


def list_report_urls() -> list[str]:
    resp = requests.get(MONITORING_URL, headers=HEADERS)
    resp.raise_for_status()
    urls = sorted(set(REPORT_URL_RE.findall(resp.text)))
    if not urls:
        raise RuntimeError('No RTA2 weekly-report links found; '
                           'the monitoring page layout may have changed.')
    return urls


def download_new(urls: list[str]) -> list[pl.Path]:
    DIR_PDF.mkdir(parents=True, exist_ok=True)
    paths = []
    for url in urls:
        path = DIR_PDF / url.rsplit('/', 1)[1]
        if not path.exists():
            print(f'  downloading {path.name}')
            resp = requests.get(url, headers=HEADERS)
            resp.raise_for_status()
            path.write_bytes(resp.content)
        paths.append(path)
    return paths


def parse_pdf(path: pl.Path) -> pd.DataFrame:
    """Extracts every appendix turbidity table from one weekly report."""
    records = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table or len(table) < 3:
                continue
            # A turbidity table starts with a 'Date' column and carries
            # station names in header row 2; map each station by name.
            if str(table[0][0] or '').strip().lower() != 'date':
                continue
            header = [str(c or '').strip().lower() for c in table[1]]
            if 'ambient' not in header:
                continue
            station_cols = {}   # column index -> db column
            for idx, name in enumerate(header):
                if name in STATIONS and STATIONS[name] not in station_cols.values():
                    station_cols[idx] = STATIONS[name]
            unknown = [h for h in header[2:5] if h and h not in STATIONS]
            if unknown:
                print(f'  {path.name}: unknown station(s) {unknown}, '
                      'update STATIONS in turbidity_rta2.py')
            for row in table[2:]:
                cells = [str(c or '').strip() for c in row]
                if not (DATE_RE.match(cells[0]) and TIME_RE.match(cells[1])):
                    continue
                rec = {'date': cells[0], 'time': cells[1],
                       'source_report': path.name}
                for idx, col in station_cols.items():
                    rec[col] = cells[idx] if idx < len(cells) else None
                records.append(rec)

    df = pd.DataFrame(records)
    if df.empty:
        print(f'  {path.name}: no turbidity tables found')
        return df
    df['date'] = pd.to_datetime(df['date'], format='mixed', errors='coerce').dt.date
    df['time'] = pd.to_datetime(df['time'], format='mixed', errors='coerce').dt.time
    df = df.dropna(subset=['date', 'time'])
    for col in STATIONS.values():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        else:
            df[col] = pd.NA
    return df


def get_data(limit=None) -> pd.DataFrame:
    urls = list_report_urls()
    print(f'{len(urls)} RTA2 weekly reports listed on the monitoring page')
    if limit:
        urls = urls[-limit:]
    paths = download_new(urls)

    frames = []
    for path in paths:
        df = parse_pdf(path)
        if not df.empty:
            print(f'  {path.name}: {len(df)} readings, '
                  f'{df.date.min()} to {df.date.max()}')
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    # Overlapping reports (rare revisions) resolve to the last parsed.
    df = df.sort_values(['date', 'time']).drop_duplicates(['date', 'time'], keep='last')
    return df[['date', 'time', 'ambient', 'n3sb', 'tb4', 'source_report']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='parse and summarize without writing to the database')
    parser.add_argument('--limit', type=int, default=None,
                        help='only process the N newest reports')
    args = parser.parse_args()

    df = get_data(limit=args.limit)
    print(f'\nTotal: {len(df)} readings, {df.date.min()} to {df.date.max()}')

    if args.dry_run:
        print('Dry run: nothing written to the database.')
        return

    apply_schema.apply()
    write_to_db.write_df_to_table(df, TABLE_NAME, pk_cols=['date', 'time'])


if __name__ == '__main__':
    main()
