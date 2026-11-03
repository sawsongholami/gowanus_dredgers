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

import pandas as pd
import sqlalchemy as sa
import streamlit as st

# EPA Beach Action Value for Enterococcus, single sample: 110 MPN/100 mL.
SWIM_THRESHOLD_MPN = 110
# NY State chronic standard for dissolved oxygen in Class SD waters: 5 mg/L.
DO_STANDARD_MG_L = 5.0

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


@st.cache_data(ttl=DATA_TTL, show_spinner='Loading Enterococcus samples...')
def enterococcus():
    """One row per CWQT sample with a result, plus 72-hour rain in inches.

    Rain is the CWQT programme's own Central Park gauge columns, not our
    modelled `weather` table -- see the weather note in README.md.
    """
    df = _read("""
        SELECT date, site, mpn,
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
