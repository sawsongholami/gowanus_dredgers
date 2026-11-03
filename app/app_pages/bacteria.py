"""Enterococcus: how often the canal is over the swim threshold, and rain's part in it."""

import altair as alt
import streamlit as st

import access
import charts
import data

access.require('bacteria')

st.title('Bacteria (Enterococcus)')
df = data.enterococcus()
threshold = data.SWIM_THRESHOLD_MPN

c1, c2, c3 = st.columns(3)
c1.metric('Samples', f'{len(df):,}')
c2.metric(f'Over {threshold} MPN', f'{df.over_threshold.mean():.0%}')
c3.metric('Years', f'{df.year.min()}–{df.year.max()}')

st.caption(f'{threshold} MPN/100 mL is the EPA Beach Action Value: above it, a beach would be '
           'posted as unsafe for swimming. Results reported as "<10" are plotted at 10, and '
           '">24,196" at 24,196. Sampling is weekly, mostly Thursdays, May to October.')

# --- Every sample, by year --------------------------------------------------
# Each dot is one sample, so a year's spread and its sample count are both
# visible -- a share-over-threshold bar hides how few samples some years had.
st.subheader('Every sample, by year')
log_y = alt.Y('mpn:Q', scale=alt.Scale(type='log'), title='Enterococcus (MPN/100 mL, log scale)')
dots = alt.Chart(df).mark_circle(size=40, opacity=0.45, color=charts.series()[0]).encode(
    x=alt.X('year:O', title=None),
    # Jitter within the middle of each year's band, leaving gaps between years.
    xOffset=alt.XOffset('jitter:Q', scale=alt.Scale(domain=[-0.5, 1.5])),
    y=log_y,
    tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), 'site:N', alt.Tooltip('mpn:Q', format=',')],
).transform_calculate(jitter='random()')
st.altair_chart(dots + charts.threshold_rule(threshold, f'{threshold} MPN'), width='stretch')

# --- Rain before sampling ---------------------------------------------------
st.subheader('Rain in the 72 hours before sampling')
rain = df.dropna(subset=['rain_72h_in'])
only_wet = st.toggle('Only samples after some rain', value=False,
                     help='Leaves out samples with no rain in the 72 hours before.')
if only_wet:
    rain = rain[rain.rain_72h_in > 0]

scatter = alt.Chart(rain).mark_circle(size=40, opacity=0.5, color=charts.series()[0]).encode(
    # Square-root scale: most samples follow little or no rain, and a linear
    # axis crushes them against zero.
    x=alt.X('rain_72h_in:Q', scale=alt.Scale(type='sqrt'),
            title='Rain in the previous 72 hours (inches, Central Park gauge; square-root scale)'),
    y=log_y,
    tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), 'site:N',
             alt.Tooltip('rain_72h_in:Q', title='rain (in)'), alt.Tooltip('mpn:Q', format=',')],
)
st.altair_chart(scatter + charts.threshold_rule(threshold, f'{threshold} MPN'), width='stretch')

dry = rain[rain.rain_72h_in < 0.1]
wet = rain[rain.rain_72h_in >= 0.25]
if len(dry) and len(wet):
    st.caption(f'After under 0.1 in of rain, {dry.over_threshold.mean():.0%} of {len(dry):,} samples '
               f'were over the threshold. After 0.25 in or more, {wet.over_threshold.mean():.0%} '
               f'of {len(wet):,} were.')

# --- By site ------------------------------------------------------------------
st.subheader('By site')
by_site = df.groupby('site').agg(
    samples=('mpn', 'size'),
    median_mpn=('mpn', 'median'),
    p90_mpn=('mpn', lambda s: s.quantile(0.9)),
    pct_over=('over_threshold', 'mean'),
).reset_index().sort_values('median_mpn', ascending=False)
st.dataframe(
    by_site, hide_index=True,
    column_config={
        'site': 'Site',
        'samples': 'Samples',
        'median_mpn': st.column_config.NumberColumn('Median MPN', format='%.0f'),
        'p90_mpn': st.column_config.NumberColumn('90th percentile MPN', format='%.0f'),
        'pct_over': st.column_config.ProgressColumn(f'Share over {threshold}', format='percent',
                                                    min_value=0, max_value=1),
    },
)
