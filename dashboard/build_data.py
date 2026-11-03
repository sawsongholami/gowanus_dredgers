"""
Builds the dashboard's data file: dashboard/data/dashboard.json

The dashboard is a static page -- no server, no database connection from the
browser. This script is the only thing that touches the data: it reads the
database (preferred) or the local CSV snapshot in data/exports/ (fallback),
aggregates, and writes one small JSON file the page fetches.

    python dashboard/build_data.py              # database, else snapshot
    python dashboard/build_data.py --snapshot   # force the local snapshot

Why aggregate here rather than in the browser: everything this script writes
becomes public the moment the page is published. Only summary figures go into
the JSON -- no row-level readings, and nothing at all from `observations`,
which carries pseudonymous volunteer submissions. See the publishing note in
README.md before putting this on a public site.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.join(REPO, 'data', 'exports')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'dashboard.json')
# The page loads the .js twin with a <script> tag rather than fetch()ing the
# .json, so it works when opened straight off disk -- fetch() from a file://
# page is blocked by CORS. The .json is the same payload for anything else
# that wants the numbers.
OUT_JS = OUT.replace('.json', '.js')

# EPA Beach Action Value for Enterococcus, single sample: 110 MPN/100 mL.
# Above this a beach would be posted as unsafe for swimming.
SWIM_THRESHOLD_MPN = 110
# NY State chronic standard for dissolved oxygen in Class SD waters: 5 mg/L.
DO_STANDARD_MG_L = 5.0


def _from_database():
    """Reads the views. Returns None if the database is unreachable."""
    sys.path.insert(0, os.path.join(REPO, 'data_import'))
    try:
        from write_to_db import get_engine
        engine = get_engine()
        frames = {
            'cwqt': pd.read_sql('SELECT * FROM cwqt', engine),
            'duro': pd.read_sql('SELECT * FROM duro_filtered', engine),
            'rta1': pd.read_sql('SELECT * FROM turbidity_rta1', engine),
            'rta2': pd.read_sql('SELECT * FROM turbidity_rta2', engine),
            'zones': pd.read_sql('SELECT * FROM site_zones', engine),
        }
        print('  read from the database')
        return frames
    except Exception as exc:
        print(f'  database unreachable ({type(exc).__name__}), falling back to the snapshot')
        print(f'    {str(exc).splitlines()[0][:160]}')
        return None


def _from_snapshot():
    """Reads data/exports/*.csv and applies duro_filtered's filter by hand."""
    duro = pd.read_csv(os.path.join(EXPORTS, 'duro.csv'), parse_dates=['observed_at'])
    # Same predicate as the duro_filtered view: a known site, in the water.
    duro = duro[duro.site.notna() & (duro.site != 'TBD') & (~duro.flag_out_of_water.astype(bool))]
    print('  read from the CSV snapshot in data/exports/')
    return {
        'cwqt': pd.read_csv(os.path.join(EXPORTS, 'cwqt.csv'), parse_dates=['date']),
        'duro': duro,
        'rta1': pd.read_csv(os.path.join(EXPORTS, 'turbidity_rta1.csv'), parse_dates=['date']),
        'rta2': pd.read_csv(os.path.join(EXPORTS, 'turbidity_rta2.csv'), parse_dates=['date']),
        'zones': None,
    }


def _site_label(slug):
    """Second_St -> Second St, for display."""
    return str(slug).replace('_', ' ')


def build(frames, source):
    cwqt, duro = frames['cwqt'], frames['duro']
    rta1, rta2 = frames['rta1'], frames['rta2']

    cwqt['date'] = pd.to_datetime(cwqt['date'])
    cwqt['year'] = cwqt['date'].dt.year
    sampled = cwqt[cwqt.mpn.notna()].copy()

    # --- Headline figures -------------------------------------------------
    headline = {
        'years_of_record': int(cwqt.year.max() - cwqt.year.min() + 1),
        'entero_samples': int(len(sampled)),
        'pct_over_threshold': round(100 * (sampled.mpn > SWIM_THRESHOLD_MPN).mean(), 0),
        'duro_readings': int(len(duro)),
        'duro_outings': int(duro.observed_at.dt.date.nunique()),
        'duro_sites': int(duro.site.nunique()),
        'turbidity_readings': int(len(rta1) + len(rta2)),
        'first_sample': cwqt.date.min().strftime('%b %Y'),
        'last_sample': cwqt.date.max().strftime('%b %Y'),
    }

    # --- Enterococcus: share of samples above the swim threshold, by year --
    by_year = sampled.groupby('year').agg(
        n=('mpn', 'size'),
        median_mpn=('mpn', 'median'),
        pct_over=('mpn', lambda s: round(100 * (s > SWIM_THRESHOLD_MPN).mean(), 1)),
    ).reset_index()
    entero_by_year = by_year.to_dict('records')

    # --- Enterococcus by site ---------------------------------------------
    by_site = sampled.groupby('site').agg(
        n=('mpn', 'size'),
        median_mpn=('mpn', 'median'),
        p90_mpn=('mpn', lambda s: round(float(s.quantile(0.9)), 0)),
        pct_over=('mpn', lambda s: round(100 * (s > SWIM_THRESHOLD_MPN).mean(), 1)),
    ).reset_index().sort_values('median_mpn', ascending=False)
    by_site['label'] = by_site.site.map(_site_label)
    entero_by_site = by_site.to_dict('records')

    # --- Rain -> bacteria --------------------------------------------------
    # The 72-hour antecedent rainfall window, from the CWQT programme's own
    # precipitation columns (Central Park gauge, inches). Those are gauge
    # readings, unlike our `weather` table, which is modelled on a ~9 km grid
    # centred 4.5 km inland -- see the weather note in README.md.
    rain_cols = ['precip_on_collection_day',
                 'precip_1_day_before_collection',
                 'precip_2_days_before_collection']
    rain = sampled.dropna(subset=rain_cols + ['mpn']).copy()
    rain['rain_72h_in'] = rain[rain_cols].sum(axis=1).round(2)
    rain_vs_mpn = [
        {'rain': float(r.rain_72h_in), 'mpn': float(r.mpn), 'site': _site_label(r.site),
         'date': r.date.strftime('%Y-%m-%d')}
        for r in rain.itertuples()
    ]
    # The same story as two numbers, for the caption.
    dry = rain[rain.rain_72h_in < 0.1]
    wet = rain[rain.rain_72h_in >= 0.25]
    rain_summary = {
        'dry_n': int(len(dry)),
        'dry_pct_over': round(100 * (dry.mpn > SWIM_THRESHOLD_MPN).mean(), 0) if len(dry) else None,
        'dry_median': round(float(dry.mpn.median()), 0) if len(dry) else None,
        'wet_n': int(len(wet)),
        'wet_pct_over': round(100 * (wet.mpn > SWIM_THRESHOLD_MPN).mean(), 0) if len(wet) else None,
        'wet_median': round(float(wet.mpn.median()), 0) if len(wet) else None,
    }

    # --- Dissolved oxygen by site (Duro sonde) -----------------------------
    do = duro[duro.do_mg_l.notna()]
    do_site = do.groupby('site').agg(
        n=('do_mg_l', 'size'),
        mean_do=('do_mg_l', 'mean'),
        p10_do=('do_mg_l', lambda s: float(s.quantile(0.1))),
        pct_below=('do_mg_l', lambda s: round(100 * (s < DO_STANDARD_MG_L).mean(), 1)),
    ).reset_index()
    # Sites with a handful of readings are noise on a chart of averages.
    do_site = do_site[do_site.n >= 100].sort_values('mean_do')
    do_site['label'] = do_site.site.map(_site_label)
    do_site['mean_do'] = do_site.mean_do.round(2)
    do_site['p10_do'] = do_site.p10_do.round(2)
    do_by_site = do_site.to_dict('records')

    # --- Turbidity, the two dredging eras ----------------------------------
    # RTA1 and RTA2 are different stretches of canal, monitored in sequence,
    # with different buoys -- kept as two series precisely so the page cannot
    # imply one continuous instrument record. Only the `ambient` column is
    # plotted, the one station label both eras share. Weekly medians: the
    # 15-minute series is spiky and a dredging plume is a tail event, so the
    # median is the readable line and p90 carries the spikes.
    def weekly(df, label):
        d = df[['date', 'ambient']].dropna().copy()
        d['date'] = pd.to_datetime(d['date'])
        d['week'] = d['date'].dt.to_period('W').dt.start_time
        g = d.groupby('week').agg(
            median_ntu=('ambient', 'median'),
            p90_ntu=('ambient', lambda s: float(s.quantile(0.9))),
            n=('ambient', 'size'),
        ).reset_index()
        g = g[g.n >= 50]   # drop part-weeks, which swing wildly
        return [
            {'week': r.week.strftime('%Y-%m-%d'),
             'median_ntu': round(float(r.median_ntu), 2),
             'p90_ntu': round(float(r.p90_ntu), 2),
             'phase': label}
            for r in g.itertuples()
        ]

    turbidity = {'rta1': weekly(rta1, 'RTA1'), 'rta2': weekly(rta2, 'RTA2')}

    # --- Data currency ------------------------------------------------------
    as_of = max(cwqt.date.max(),
                pd.to_datetime(duro.observed_at.max()),
                pd.to_datetime(rta2.date.max()))

    return {
        'meta': {
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            'source': source,
            'data_as_of': as_of.strftime('%Y-%m-%d'),
            'swim_threshold_mpn': SWIM_THRESHOLD_MPN,
            'do_standard_mg_l': DO_STANDARD_MG_L,
        },
        'headline': headline,
        'entero_by_year': entero_by_year,
        'entero_by_site': entero_by_site,
        'rain_vs_mpn': rain_vs_mpn,
        'rain_summary': rain_summary,
        'do_by_site': do_by_site,
        'turbidity': turbidity,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--snapshot', action='store_true',
                    help='skip the database and read data/exports/*.csv')
    args = ap.parse_args()

    print('Building dashboard data...')
    frames, source = None, None
    if not args.snapshot:
        frames = _from_database()
        source = 'database'
    if frames is None:
        frames = _from_snapshot()
        source = 'snapshot'

    payload = build(frames, source)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as fh:
        json.dump(payload, fh, indent=1)
    with open(OUT_JS, 'w') as fh:
        fh.write('window.DASHBOARD_DATA = ')
        json.dump(payload, fh, indent=1)
        fh.write(';\n')

    h = payload['headline']
    print(f"  wrote {OUT} ({os.path.getsize(OUT) / 1024:.0f} KB) and its .js twin")
    print(f"  source={source}  data as of {payload['meta']['data_as_of']}")
    print(f"  {h['entero_samples']} Enterococcus samples, "
          f"{h['pct_over_threshold']:.0f}% over {SWIM_THRESHOLD_MPN} MPN; "
          f"{h['duro_outings']} sonde outings")


if __name__ == '__main__':
    main()
