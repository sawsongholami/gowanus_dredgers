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
gm_standard = data.GEO_MEAN_STANDARD_MPN

st.markdown(f"""
Mostly not, and least of all after rain. Volunteers collect a water sample
most Thursdays from May to October, and a lab counts **Enterococcus**: gut
bacteria that show sewage is in the water. In heavy rain the sewers
overflow into the canal, and the count jumps.

New York State sets two lines for swimming beaches, in MPN (bacteria per
100 mL of water). **No single sample may be over {threshold} MPN**, and over
any 30 days, the **geometric mean of five or more samples may not be over
{gm_standard} MPN**. A beach that fails either is closed to swimming.
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
RATING_NOTE = (f'**Rating** follows the Citizens\' Water Quality Testing programme: a geometric mean of '
               f'{gm_standard} MPN or less is *good*, over {gm_standard} up to {threshold} is *advisory*, and '
               f'over {threshold} is *poor*. The state standard applies {gm_standard} MPN to 30-day '
               'stretches of sampling, so a geometric mean over a whole year or a whole site\'s record '
               'is a yardstick for comparison, not a pass or fail.')

# --- Every sample, by year --------------------------------------------------
# Each dot is one sample, so a year's spread and its sample count are both
# visible -- a share-over-threshold bar hides how few samples some years had.
sections.heading('Has the water been getting cleaner?')
st.markdown('**Every sample, by year.** Each dot is one sample, judged against the '
            f'{threshold} MPN single-sample line. The orange bar is that year\'s geometric mean, '
            f'judged against the orange {gm_standard} MPN line. If the canal were getting cleaner, '
            'the bars would step down.')

yearly = df.groupby('year').agg(
    geo_mean=('mpn', data.geo_mean), samples=('mpn', 'size'), pct_over=('over_threshold', 'mean'),
).reset_index()
yearly.insert(2, 'rating', yearly.geo_mean.map(data.rating))
years = sorted(df.year.unique())
picked = st.selectbox('Year', ['All years'] + [str(y) for y in reversed(years)],
                      help='Pick one year to see its samples week by week.')
rule = charts.threshold_rule(threshold, f'{threshold} MPN, single sample')
geo_color = charts.series()[1]
gm_rule = charts.threshold_rule(gm_standard, f'{gm_standard} MPN, geometric mean', color=geo_color)

# Year labels at 45 degrees: Altair stands them on end by default.
year_x = alt.X('year:O', title=None, axis=alt.Axis(labelAngle=-45))

if picked == 'All years':
    shown = df
    dots = alt.Chart(df).mark_circle(size=40, opacity=0.45, color=charts.series()[0]).encode(
        x=year_x,
        # Jitter within the middle of each year's band, leaving gaps between years.
        xOffset=alt.XOffset('jitter:Q', scale=alt.Scale(domain=[-0.5, 1.5])),
        y=log_y,
        tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), 'site:N', alt.Tooltip('mpn:Q', format=',')],
    ).transform_calculate(jitter='random()')
    marks = alt.Chart(yearly).mark_tick(color=geo_color, thickness=3, size=36).encode(
        x=year_x,
        y=alt.Y('geo_mean:Q', scale=alt.Scale(type='log')),
        tooltip=[alt.Tooltip('year:O'), alt.Tooltip('geo_mean:Q', title='geometric mean (MPN)', format=',.0f'),
                 alt.Tooltip('rating:N'), alt.Tooltip('samples:Q'),
                 alt.Tooltip('pct_over:Q', title=f'over {threshold}', format='.0%')],
    )
    st.altair_chart(dots + marks + rule + gm_rule, width='stretch')
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
    gm_line = alt.Chart(gm).mark_rule(color=geo_color, strokeWidth=3).encode(y='y:Q')
    gm_text = alt.Chart(gm).mark_text(align='right', dx=-4, dy=-8, color=geo_color, fontWeight='bold').encode(
        y='y:Q', x=alt.value('width'), text='label:N')
    st.altair_chart(dots + gm_line + gm_text + rule + gm_rule, width='stretch')
    st.caption(f'{picked}: {stats.samples:,.0f} samples, {stats.pct_over:.0%} over {threshold} MPN; '
               f'geometric mean {stats.geo_mean:,.0f} MPN ({stats.rating}).')

with st.expander('How to read this'):
    st.markdown(GEO_MEAN_NOTE + '\n\n' + RATING_NOTE + '\n\n'
                'The axis is a **log scale**: each gridline is ten times the one below, because '
                'counts run from under 10 to over 24,000. Years have between '
                f'{yearly.samples.min()} and {yearly.samples.max()} samples, so a single '
                "year's bar can move a lot on a few stormy Thursdays.")
    st.dataframe(yearly, hide_index=True, column_config={
        'year': st.column_config.NumberColumn('Year', format='%d'),
        'geo_mean': st.column_config.NumberColumn('Geometric mean (MPN)', format='%.0f'),
        'rating': 'Rating',
        'samples': 'Samples',
        'pct_over': st.column_config.NumberColumn(f'Share over {threshold}', format='percent'),
    })
site_map.show({'Sampled for bacteria' + ('' if picked == 'All years' else f' in {picked}'):
               sorted(shown.site.unique())})

# --- The state's 30-day test ------------------------------------------------
# How the state actually applies 35 MPN: a site's geometric mean over 30 days,
# counted only when those 30 days hold five or more samples.
sections.heading("Did it pass the state's 30-day test?")
st.markdown(f'**Share of 30-day stretches that met the {gm_standard} MPN standard, by year.** '
            f'For every day a site was sampled, this takes the geometric mean of that site\'s '
            f'samples over the 30 days ending that day, as the state does for beaches. Stretches '
            f'with fewer than {data.GEO_MEAN_MIN_SAMPLES} samples are left out, because the standard '
            'needs five. A taller bar is a cleaner year.')
windows = data.rolling_geo_mean(df)
counted = windows[windows.qualifies]
if len(counted):
    by_year = counted.groupby('year').agg(
        stretches=('rating', 'size'),
        good=('rating', lambda r: (r == 'good').mean()),
        advisory=('rating', lambda r: (r == 'advisory').mean()),
        poor=('rating', lambda r: (r == 'poor').mean()),
        sites=('site', 'nunique'),
    ).reset_index()
    by_year['left_out'] = by_year.year.map(windows[~windows.qualifies].groupby('year').size()).fillna(0).astype(int)
    bars = alt.Chart(by_year).mark_bar(color=charts.series()[0], cornerRadiusTopLeft=4,
                                       cornerRadiusTopRight=4).encode(
        x=year_x,
        y=alt.Y('good:Q', title=f'30-day stretches at or under {gm_standard} MPN',
                axis=alt.Axis(format='%'), scale=alt.Scale(domain=[0, 1])),
        tooltip=[alt.Tooltip('year:O'),
                 alt.Tooltip('good:Q', title=f'met {gm_standard} (good)', format='.0%'),
                 alt.Tooltip('advisory:Q', title='advisory', format='.0%'),
                 alt.Tooltip('poor:Q', title=f'over {threshold} (poor)', format='.0%'),
                 alt.Tooltip('stretches:Q', title='stretches counted'),
                 alt.Tooltip('sites:Q')],
    )
    st.altair_chart(bars, width='stretch')
    st.caption(f'Across all years, {counted.rating.eq("good").mean():.0%} of {len(counted):,} counted '
               f'30-day stretches met {gm_standard} MPN and {counted.rating.eq("poor").mean():.0%} were '
               f'over {threshold}. Stretches overlap, since each sampling day ends one.')
    with st.expander('The numbers'):
        st.markdown(RATING_NOTE.split(' The state standard')[0])
        st.dataframe(by_year, hide_index=True, column_config={
            'year': st.column_config.NumberColumn('Year', format='%d'),
            'stretches': 'Stretches counted',
            'good': st.column_config.NumberColumn('Good', format='percent'),
            'advisory': st.column_config.NumberColumn('Advisory', format='percent'),
            'poor': st.column_config.NumberColumn('Poor', format='percent'),
            'sites': 'Sites',
            'left_out': st.column_config.NumberColumn('Left out (under 5 samples)'),
        })
else:
    st.info(f'No site has {data.GEO_MEAN_MIN_SAMPLES} samples within 30 days, so the test can\'t be applied.')

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
               f'were over {threshold} MPN (geometric mean {data.geo_mean(dry.mpn):,.0f} MPN). '
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
               f'{near_high.over_threshold.mean():.0%} of {len(near_high):,} samples over {threshold} MPN. '
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
by_site.insert(3, 'rating', by_site.geo_mean.map(data.rating))
st.dataframe(
    by_site, hide_index=True,
    column_config={
        'site': 'Site',
        'samples': 'Samples',
        'geo_mean': st.column_config.NumberColumn('Geometric mean (MPN)', format='%.0f'),
        'rating': 'Rating',
        'pct_over': st.column_config.ProgressColumn(f'Share over {threshold}', format='percent',
                                                    min_value=0, max_value=1),
        'first': st.column_config.NumberColumn('First year', format='%d'),
        'last': st.column_config.NumberColumn('Last year', format='%d'),
    },
)
st.caption('Sites were sampled in different years and in different numbers, so a site with few '
           'samples can rank high or low by chance. ' + RATING_NOTE.replace('**Rating**', 'Rating'))
site_map.show({'Sampled for bacteria': sorted(df.site.unique())})

# --- The city's Harbor Survey ---------------------------------------------------
sections.heading("Does the city's own survey agree?")
st.markdown('**Yearly geometric mean, CWQT and the city.** The city\'s Department of Environmental '
            'Protection also counts Enterococcus in the canal, about once a month from a boat, as part '
            'of its Harbor Survey. Orange is CWQT\'s yearly geometric mean (the bars in the first chart); '
            f'aqua is the city\'s. The dashed orange line is the {gm_standard} MPN geometric-mean standard.')
hs = data.harbor_survey()
hs = hs[hs.enterococci > 0]
CWQT, CITY = 'CWQT (volunteers)', 'City Harbor Survey'
compare = pd.concat([
    yearly.assign(source=CWQT)[['year', 'geo_mean', 'source']],
    hs.groupby('year').enterococci.agg(data.geo_mean).rename('geo_mean').reset_index().assign(source=CITY),
], ignore_index=True)
compare = compare[compare.year >= min(years)] if len(years) else compare
if len(hs) and len(compare):
    colors = charts.series()
    lines = alt.Chart(compare).mark_line(point=alt.OverlayMarkDef(size=60), strokeWidth=2).encode(
        x=year_x,
        y=alt.Y('geo_mean:Q', scale=alt.Scale(type='log'), title='Geometric mean (MPN/100 mL, log scale)'),
        color=alt.Color('source:N', title=None, legend=alt.Legend(orient='top', labelLimit=0),
                        scale=alt.Scale(domain=[CWQT, CITY], range=[geo_color, colors[charts.CITY_SURVEY]])),
        tooltip=['year:O', 'source:N', alt.Tooltip('geo_mean:Q', title='geometric mean', format=',.0f')],
    )
    st.altair_chart(lines + gm_rule, width='stretch')
    cwqt_day = df.groupby('date').mpn.agg(data.geo_mean).rename('cwqt')
    city_day = hs.groupby('date').enterococci.agg(data.geo_mean).rename('city')
    same = cwqt_day.to_frame().join(city_day, how='inner')
    if len(same):
        st.caption(f'On the {len(same)} days both programmes sampled, CWQT\'s geometric mean was '
                   f'{data.geo_mean(same.cwqt):,.0f} MPN and the city\'s {data.geo_mean(same.city):,.0f}. '
                   'They sample different spots, depths and times of day (the city near the surface '
                   'mid-channel from a boat, CWQT from the bank), so their counts differ even on the '
                   'same day. Source: NYC DEP Harbor Survey, NYC Open Data.')
    with st.expander('The numbers, by year'):
        wide = compare.pivot(index='year', columns='source', values='geo_mean').reset_index()
        st.dataframe(wide, hide_index=True, column_config={
            'year': st.column_config.NumberColumn('Year', format='%d'),
            CWQT: st.column_config.NumberColumn(CWQT + ' (MPN)', format='%.0f'),
            CITY: st.column_config.NumberColumn(CITY + ' (MPN)', format='%.0f'),
        })

st.caption('Source: Citizens\' Water Quality Testing programme (SwimmableNYC and the Billion Oyster '
           f'Project). Standards: New York State bathing-beach rules (10 NYCRR Subpart 6-2), '
           f'{threshold} MPN/100 mL for a single sample and {gm_standard} for a 30-day geometric mean.')
