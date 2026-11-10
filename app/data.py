"""
Database reads for the app.

The app connects as app_reader, a read-only login that can SELECT the views
and summary tables it charts and nothing else -- not `duro` directly, not
`observations` (see db/app_reader.sql). It never uses the owner login in
.env, which can drop tables: if the app's credentials ever leak, the worst
case is someone reading what the team can already see.

Credentials come from st.secrets ([database] in .streamlit/secrets.toml
locally, the secrets.toml Secret File on Render).

Aggregation follows the same rules as the static dashboard's build_data.py
so the two agree: weekly turbidity medians over full weeks only, DO sites
with at least 100 readings, the EPA swim threshold for Enterococcus.
"""

import numpy as np
import pandas as pd
import sqlalchemy as sa
import streamlit as st

# EPA Beach Action Value for Enterococcus, single sample: 110 MPN/100 mL.
SWIM_THRESHOLD_MPN = 110
# NY State chronic standard for dissolved oxygen in Class SD waters: 5 mg/L.
DO_STANDARD_MG_L = 5.0

# Average time from one high tide to the next, in hours.
TIDE_CYCLE_H = 12.42

# The data explorer's measures: one value per day for the whole canal.
# mark: how the explorer draws it; log: bacteria counts span four orders of
# magnitude, so they get a log axis.
MEASURES = {
    'Enterococcus (MPN/100 mL)':       {'mark': 'point', 'log': True,
                                        'what': 'Geometric mean of the day\'s samples, all sites (CWQT)'},
    'Dissolved oxygen (mg/L)':         {'mark': 'point', 'log': False,
                                        'what': 'Average of the day\'s sonde readings, all sites (Duro)'},
    'Water temperature (°C)':          {'mark': 'point', 'log': False,
                                        'what': 'Average of the day\'s sonde readings, all sites (Duro)'},
    'Salinity (ppt)':                  {'mark': 'point', 'log': False,
                                        'what': 'Average of the day\'s sonde readings, all sites (Duro)'},
    'Turbidity (NTU)':                 {'mark': 'point', 'log': False,
                                        'what': 'Median of the day\'s readings at the ambient buoy (Superfund monitoring)'},
    'Rain (mm per day)':               {'mark': 'bar', 'log': False,
                                        'what': 'Daily total from a weather model, not a gauge at the canal (Open-Meteo)'},
    'Air temperature (°C)':            {'mark': 'line', 'log': False,
                                        'what': 'Daily average from a weather model (Open-Meteo)'},
    'Highest high tide (m, predicted)': {'mark': 'line', 'log': False,
                                        'what': 'The higher of the day\'s predicted high tides at Gowanus Bay (NOAA)'},
}

# How long a chart's data is reused before re-querying. The loaders run by
# hand at most daily, so six hours keeps the page fast without going stale.
DATA_TTL = '6h'
# A removed viewer loses access within this long.
VIEWER_TTL = '60s'


@st.cache_resource
def _engine():
    db = st.secrets['database']
    url = sa.URL.create(
        'postgresql+psycopg2',
        username=db['user'],
        password=db['password'],
        host=db['host'],
        port=int(db.get('port', 6543)),
        database='postgres',
    )
    return sa.create_engine(url, pool_pre_ping=True)


def _read(sql, **params):
    with _engine().connect() as conn:
        return pd.read_sql(sa.text(sql), conn, params=params)


@st.cache_data(ttl=VIEWER_TTL, show_spinner=False)
def viewer_role(email):
    df = _read('SELECT role FROM app_viewers WHERE email = :email', email=email)
    return df.role.iloc[0] if len(df) else None


@st.cache_data(ttl=VIEWER_TTL, show_spinner=False)
def viewers():
    return _read('SELECT email, role, note, added_at FROM app_viewers ORDER BY role, email')


def geo_mean(values):
    """Geometric mean: the usual summary for bacteria counts, which multiply
    rather than add. Censored results enter at their reporting limit ("<10"
    as 10), the same way they are stored."""
    values = pd.Series(values).dropna()
    return float(np.exp(np.log(values).mean())) if len(values) else float('nan')


def _hours(times):
    """A column of clock times as hours since midnight (NaN where missing)."""
    return times.map(lambda t: t.hour + t.minute / 60 if t is not None and not pd.isna(t) else np.nan)


@st.cache_data(ttl=DATA_TTL, show_spinner='Loading Enterococcus samples...')
def enterococcus():
    """One row per CWQT sample with a result, plus 72-hour rain in inches
    and where the tide was when the sample was taken.

    Rain is the CWQT programme's own Central Park gauge columns, not our
    modelled `weather` table -- see the weather note in README.md.

    hours_from_high_tide comes from the programme's own Battery high-tide
    time for the day: negative is before high tide (rising), positive after
    (falling), about +/-6.2 is low tide. The sheet gives one high tide a day
    and there are two, so the gap is wrapped onto the nearest one.
    """
    df = _read("""
        SELECT date, site, mpn, sample_time, battery_high_tide,
               precip_on_collection_day
             + precip_1_day_before_collection
             + precip_2_days_before_collection AS rain_72h_in
        FROM cwqt
        WHERE mpn IS NOT NULL
    """)
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.year
    df['site'] = df['site'].str.replace('_', ' ')
    df['over_threshold'] = df['mpn'] > SWIM_THRESHOLD_MPN
    gap = _hours(df.pop('sample_time')) - _hours(df.pop('battery_high_tide'))
    df['hours_from_high_tide'] = ((gap + TIDE_CYCLE_H / 2) % TIDE_CYCLE_H - TIDE_CYCLE_H / 2).round(2)
    return df


@st.cache_data(ttl=DATA_TTL, show_spinner='Loading dissolved oxygen...')
def oxygen_by_site():
    df = _read("""
        SELECT d.site,
               z.rta_zone,
               count(*)                                                 AS n,
               avg(do_mg_l)                                             AS mean_do,
               percentile_cont(0.1) WITHIN GROUP (ORDER BY do_mg_l)     AS p10_do,
               100.0 * avg(CASE WHEN do_mg_l < :std THEN 1 ELSE 0 END)  AS pct_below,
               min(observed_at)::date                                   AS first_day,
               max(observed_at)::date                                   AS last_day
        FROM duro_filtered d
        LEFT JOIN site_zones z ON z.site = d.site
        WHERE do_mg_l IS NOT NULL
        GROUP BY d.site, z.rta_zone
        HAVING count(*) >= 100
        ORDER BY mean_do
    """, std=DO_STANDARD_MG_L)
    df['site'] = df['site'].str.replace('_', ' ')
    return df.round({'mean_do': 2, 'p10_do': 2, 'pct_below': 1})


@st.cache_data(ttl=DATA_TTL, show_spinner='Loading turbidity...')
def turbidity_weekly():
    """Weekly median and 90th percentile of the `ambient` station, per era.

    RTA1 and RTA2 are different stretches of canal with different buoys, so
    they stay two series. Weeks with under 50 readings are dropped: part-weeks
    swing wildly.
    """
    out = _read("""
        SELECT phase,
               date_trunc('week', measured_at)::date                     AS week,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY ntu)          AS median_ntu,
               percentile_cont(0.9) WITHIN GROUP (ORDER BY ntu)          AS p90_ntu,
               count(*)                                                  AS n
        FROM turbidity
        WHERE station = 'ambient'
        GROUP BY 1, 2
        HAVING count(*) >= 50
        ORDER BY 1, 2
    """)
    out['week'] = pd.to_datetime(out['week'])
    return out.round({'median_ntu': 2, 'p90_ntu': 2})


@st.cache_data(ttl=DATA_TTL, show_spinner='Loading the datasets...')
def daily_measures():
    """Every explorer measure as one value per day: columns date, measure, value.

    One shared shape (a "long" table) so the explorer can chart or pair any
    two measures without knowing where each came from. Each measure keeps
    only the days it was actually measured; nothing is filled in.
    """
    names = list(MEASURES)
    parts = [
        _read("""SELECT date, exp(avg(ln(mpn))) AS value FROM cwqt
                 WHERE mpn > 0 GROUP BY date""").assign(measure=names[0]),
        _read("""SELECT observed_at::date AS date, avg(do_mg_l) AS value FROM duro_filtered
                 WHERE do_mg_l IS NOT NULL GROUP BY 1""").assign(measure=names[1]),
        _read("""SELECT observed_at::date AS date, avg(water_temp_c) AS value FROM duro_filtered
                 WHERE water_temp_c IS NOT NULL GROUP BY 1""").assign(measure=names[2]),
        _read("""SELECT observed_at::date AS date, avg(salinity_ppt) AS value FROM duro_filtered
                 WHERE salinity_ppt IS NOT NULL GROUP BY 1""").assign(measure=names[3]),
        # Days with under 20 readings are part-days and swing wildly.
        _read("""SELECT measured_at::date AS date,
                        percentile_cont(0.5) WITHIN GROUP (ORDER BY ntu) AS value
                 FROM turbidity WHERE station = 'ambient'
                 GROUP BY 1 HAVING count(*) >= 20""").assign(measure=names[4]),
        _read("""SELECT date, rain_mm AS value FROM daily_weather
                 WHERE date <= current_date AND rain_mm IS NOT NULL""").assign(measure=names[5]),
        _read("""SELECT date, avg_temp_c AS value FROM daily_weather
                 WHERE date <= current_date AND avg_temp_c IS NOT NULL""").assign(measure=names[6]),
    ]
    try:
        parts.append(_read("""SELECT predicted_at::date AS date, max(height_m) AS value
                              FROM tide_predictions
                              WHERE tide_type = 'H' AND predicted_at::date <= current_date
                              GROUP BY 1""").assign(measure=names[7]))
    except (sa.exc.DBAPIError, pd.errors.DatabaseError):
        # The app's login hasn't been granted the tide table yet
        # (db/app_reader.sql): leave tides out rather than break the page.
        pass
    out = pd.concat(parts, ignore_index=True)
    out['date'] = pd.to_datetime(out['date'])
    out['value'] = out['value'].astype(float).round(2)
    return out[['date', 'measure', 'value']]
