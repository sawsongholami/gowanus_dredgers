"""Enterococcus: how often the canal is over the swim threshold, and what rain and tide do to it."""

import altair as alt
import pandas as pd
import streamlit as st

import access
import charts
import data
import sections
import site_map

access.require('bacteria')

st.title('Is the canal safe to swim in?')
df = data.enterococcus()
threshold = data.SWIM_THRESHOLD_MPN

st.markdown(f"""
Mostly not, and least of all after rain. Volunteers collect a water sample
most Thursdays from May to October, and a lab counts **Enterococcus**: gut
bacteria that show sewage is in the water. In heavy rain the sewers
overflow into the canal, and the count jumps.

The line to watch is **{threshold} MPN** (bacteria per 100 mL of water).
Above it, a beach would be posted as unsafe for swimming.
""")

c1, c2, c3, c4 = st.columns(4)
c1.metric('Samples', f'{len(df):,}')
c2.metric(f'Over {threshold} MPN', f'{df.over_threshold.mean():.0%}')
c3.metric('Geometric mean', f'{data.geo_mean(df.mpn):,.0f} MPN',
          help='The usual way to average bacteria counts. See "How to read this" below.')
c4.metric('Years', f'{df.year.min()}–{df.year.max()}')

log_y = alt.Y('mpn:Q', scale=alt.Scale(type='log'), title='Enterococcus (MPN/100 mL, log scale)')
GEO_MEAN_NOTE = ('The **geometric mean** is the standard summary for bacteria counts. A sample taken '
                 'after a storm can hold a thousand times more bacteria than one taken on a dry day, '
                 'so an ordinary average would be set almost entirely by that one sample. The '
                 'geometric mean averages the counts by their order of magnitude (10, 100, 1,000) '
                 'instead, so no single sample swamps the rest. Results '
                 'the lab reported as "<10" count as 10, and ">24,196" as 24,196.')

# --- Every sample, by year --------------------------------------------------
# Each dot is one sample, so a year's spread and its sample count are both
# visible -- a share-over-threshold bar hides how few samples some years had.
sections.heading('Has the water been getting cleaner?')
st.markdown('**Every sample, by year.** Each dot is one sample; the orange bar is that '
            "year's geometric mean. If the canal were getting cleaner, the bars would step down.")

yearly = df.groupby('year').agg(
    geo_mean=('mpn', data.geo_mean), samples=('mpn', 'size'), pct_over=('over_threshold', 'mean'),
).reset_index()
years = sorted(df.year.unique())
picked = st.selectbox('Year', ['All years'] + [str(y) for y in reversed(years)],
                      help='Pick one year to see its samples week by week.')
rule = charts.threshold_rule(threshold, f'{threshold} MPN')
geo_color = charts.series()[1]

if picked == 'All years':
    shown = df
    dots = alt.Chart(df).mark_circle(size=40, opacity=0.45, color=charts.series()[0]).encode(
        x=alt.X('year:O', title=None),
        # Jitter within the middle of each year's band, leaving gaps between years.
        xOffset=alt.XOffset('jitter:Q', scale=alt.Scale(domain=[-0.5, 1.5])),
        y=log_y,
        tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), 'site:N', alt.Tooltip('mpn:Q', format=',')],
    ).transform_calculate(jitter='random()')
    marks = alt.Chart(yearly).mark_tick(color=geo_color, thickness=3, size=36).encode(
        x=alt.X('year:O', title=None),
        y=alt.Y('geo_mean:Q', scale=alt.Scale(type='log')),
        tooltip=[alt.Tooltip('year:O'), alt.Tooltip('geo_mean:Q', title='geometric mean (MPN)', format=',.0f'),
                 alt.Tooltip('samples:Q'), alt.Tooltip('pct_over:Q', title=f'over {threshold}', format='.0%')],
    )
    st.altair_chart(dots + marks + rule, width='stretch')
else:
    shown = df[df.year == int(picked)]
    stats = yearly[yearly.year == int(picked)].iloc[0]
    dots = alt.Chart(shown).mark_circle(size=70, opacity=0.6, color=charts.series()[0]).encode(
        x=alt.X('date:T', title=None),
        # Same axis range as the all-years view, so years can be compared by eye.
        y=alt.Y('mpn:Q', scale=alt.Scale(type='log', domain=[df.mpn.min(), df.mpn.max()]),
                title='Enterococcus (MPN/100 mL, log scale)'),
        tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), 'site:N', alt.Tooltip('mpn:Q', format=',')],
    )
    gm = pd.DataFrame({'y': [stats.geo_mean], 'label': [f'{picked} geometric mean: {stats.geo_mean:,.0f} MPN']})
    gm_rule = alt.Chart(gm).mark_rule(color=geo_color, strokeWidth=3).encode(y='y:Q')
    gm_text = alt.Chart(gm).mark_text(align='right', dx=-4, dy=-8, color=geo_color, fontWeight='bold').encode(
        y='y:Q', x=alt.value('width'), text='label:N')
    st.altair_chart(dots + gm_rule + gm_text + rule, width='stretch')
    st.caption(f'{picked}: {stats.samples:,.0f} samples, geometric mean {stats.geo_mean:,.0f} MPN, '
               f'{stats.pct_over:.0%} over the threshold.')

with st.expander('How to read this'):
    st.markdown(GEO_MEAN_NOTE + '\n\n'
                'The axis is a **log scale**: each gridline is ten times the one below, because '
                'counts run from under 10 to over 24,000. Years have between '
                f'{yearly.samples.min()} and {yearly.samples.max()} samples, so a single '
                "year's bar can move a lot on a few stormy Thursdays.")
    st.dataframe(yearly, hide_index=True, column_config={
        'year': st.column_config.NumberColumn('Year', format='%d'),
        'geo_mean': st.column_config.NumberColumn('Geometric mean (MPN)', format='%.0f'),
        'samples': 'Samples',
        'pct_over': st.column_config.NumberColumn(f'Share over {threshold}', format='percent'),
    })
site_map.show({'Sampled for bacteria' + ('' if picked == 'All years' else f' in {picked}'):
               sorted(shown.site.unique())})

# --- Rain before sampling ---------------------------------------------------
sections.heading('What does rain do?')
st.markdown('**Rain in the 72 hours before sampling.** Each dot is one sample: further right '
            'means more rain in the three days before it was taken. Dots climbing to the right '
            'are sewer overflows reaching the canal.')
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
st.altair_chart(scatter + rule, width='stretch')

dry = rain[rain.rain_72h_in < 0.1]
wet = rain[rain.rain_72h_in >= 0.25]
if len(dry) and len(wet):
    st.caption(f'After under 0.1 in of rain, {dry.over_threshold.mean():.0%} of {len(dry):,} samples '
               f'were over the threshold (geometric mean {data.geo_mean(dry.mpn):,.0f} MPN). '
               f'After 0.25 in or more, {wet.over_threshold.mean():.0%} of {len(wet):,} were '
               f'(geometric mean {data.geo_mean(wet.mpn):,.0f} MPN).')

# --- Tide at sampling time ----------------------------------------------------
sections.heading('Does the tide matter?')
st.markdown('**Where the tide was when each sample was taken.** The canal is tidal: harbor water '
            'pushes in as the tide rises and drains out as it falls. The middle of the chart is '
            'high tide; the two edges are low tide.')
tide = df.dropna(subset=['hours_from_high_tide'])
tide_chart = alt.Chart(tide).mark_circle(size=40, opacity=0.5, color=charts.series()[0]).encode(
    x=alt.X('hours_from_high_tide:Q', scale=alt.Scale(domain=[-6.5, 6.5]),
            axis=alt.Axis(values=[-6, -4, -2, 0, 2, 4, 6]),
            title='Hours from high tide (negative: tide rising, positive: tide falling)'),
    y=log_y,
    tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), 'site:N',
             alt.Tooltip('hours_from_high_tide:Q', title='hours from high tide'),
             alt.Tooltip('mpn:Q', format=',')],
)
st.altair_chart(tide_chart + rule, width='stretch')

near_high = tide[tide.hours_from_high_tide.abs() <= 2]
near_low = tide[tide.hours_from_high_tide.abs() >= 4.2]
if len(near_high) and len(near_low):
    st.caption(f'Within 2 hours of high tide: geometric mean {data.geo_mean(near_high.mpn):,.0f} MPN, '
               f'{near_high.over_threshold.mean():.0%} of {len(near_high):,} samples over the threshold. '
               f'Within 2 hours of low tide: {data.geo_mean(near_low.mpn):,.0f} MPN, '
               f'{near_low.over_threshold.mean():.0%} of {len(near_low):,}. '
               "Tide times are the sampling programme's own, for the Battery, a few minutes off the "
               "canal's. This doesn't separate tide from rain, so read it as a first look.")

# --- By site ------------------------------------------------------------------
sections.heading('Where is it worst?')
st.markdown('**By site.** The same samples, grouped by where they were taken.')
by_site = df.groupby('site').agg(
    samples=('mpn', 'size'),
    geo_mean=('mpn', data.geo_mean),
    pct_over=('over_threshold', 'mean'),
    first=('year', 'min'),
    last=('year', 'max'),
).reset_index().sort_values('geo_mean', ascending=False)
st.dataframe(
    by_site, hide_index=True,
    column_config={
        'site': 'Site',
        'samples': 'Samples',
        'geo_mean': st.column_config.NumberColumn('Geometric mean (MPN)', format='%.0f'),
        'pct_over': st.column_config.ProgressColumn(f'Share over {threshold}', format='percent',
                                                    min_value=0, max_value=1),
        'first': st.column_config.NumberColumn('First year', format='%d'),
        'last': st.column_config.NumberColumn('Last year', format='%d'),
    },
)
st.caption('Sites were sampled in different years and in different numbers, so a site with few '
           'samples can rank high or low by chance.')
site_map.show({'Sampled for bacteria': sorted(df.site.unique())})

st.caption('Source: Citizens\' Water Quality Testing programme (SwimmableNYC and the Billion Oyster '
           f'Project). {threshold} MPN/100 mL is the EPA Beach Action Value.')
