"""Dissolved oxygen by site, from the Duro sonde."""

import altair as alt
import pandas as pd
import streamlit as st

import access
import charts
import data
import sections
import site_map

access.require('oxygen')

st.title('Can fish survive in the canal?')
st.markdown(f"""
Fish breathe oxygen dissolved in the water. When sewage and algae rot, they
use that oxygen up, and fish and crabs have to leave or die. New York
State's standard for this class of water is **{data.DO_STANDARD_MG_L:g} mg/L**;
below it, fish and other animals start to struggle.

The Dredgers measured dissolved oxygen from a canoe, with a sensor called a
sonde, on about 200 outings between August 2023 and October 2024.
""")

sections.heading('Which parts of the canal have enough oxygen?')
st.markdown('**Average dissolved oxygen by site.** One bar per site, lowest at the top. '
            'A bar that stops short of the dashed line averages below the standard.')

df = data.oxygen_by_site()

bars = alt.Chart(df).mark_bar(color=charts.series()[0], cornerRadiusEnd=4, size=14).encode(
    y=alt.Y('site:N', sort=alt.SortField('mean_do', order='ascending'), title=None),
    x=alt.X('mean_do:Q', title='Average dissolved oxygen (mg/L)'),
    tooltip=['site:N', 'rta_zone:N',
             alt.Tooltip('mean_do:Q', title='average (mg/L)'),
             alt.Tooltip('p10_do:Q', title='10th percentile (mg/L)'),
             alt.Tooltip('pct_below:Q', title=f'% below {data.DO_STANDARD_MG_L:g}'),
             alt.Tooltip('n:Q', title='readings', format=',')],
)
standard = alt.Chart(df.head(1)).mark_rule(color=charts.REFERENCE, strokeDash=[4, 4], strokeWidth=1.5).encode(
    x=alt.datum(data.DO_STANDARD_MG_L))
st.altair_chart(bars + standard, width='stretch')

st.caption('The dashed line is the 5 mg/L standard. Sites with fewer than 100 readings are left out. '
           'Readings run from August 2023 to October 2024; the sonde is now out of service. '
           'Every reading is from a daytime outing of about 40 minutes, so the overnight low, '
           "when oxygen is usually lowest, hasn't been measured.")

site_map.show({'Dissolved oxygen measured here': list(df.site)})

sections.heading('How bad does it get on a bad day?')
st.markdown('**The numbers behind the bars.** The average hides the bad days, and the bad days '
            'are what kill fish. The 10th percentile is the level on a bad day: one reading in '
            'ten was lower than this. The last number is how much of the time each site was '
            'below the standard.')
st.dataframe(
    df, hide_index=True,
    column_config={
        'site': 'Site',
        'rta_zone': 'Cleanup zone',
        'n': st.column_config.NumberColumn('Readings', format='%d'),
        'mean_do': st.column_config.NumberColumn('Average (mg/L)', format='%.2f'),
        'p10_do': st.column_config.NumberColumn('10th percentile (mg/L)', format='%.2f'),
        'pct_below': st.column_config.NumberColumn(f'% below {data.DO_STANDARD_MG_L:g} mg/L', format='%.1f'),
        'first_day': 'First reading',
        'last_day': 'Last reading',
    },
)

# --- The city's Harbor Survey ---------------------------------------------------
sections.heading("How does the city's own survey compare?")
st.markdown("**Dissolved oxygen near the surface, every measurement since 2008.** The city's "
            'Department of Environmental Protection samples the canal from a boat at fixed stations, '
            'about once a month, as part of its Harbor Survey. Each aqua dot is one of those samples; '
            "each blue dot is one day's average from the Dredgers' sonde. The dashed line is the "
            f'{data.DO_STANDARD_MG_L:g} mg/L standard.')
hs = data.harbor_survey()
hs = hs[hs.do_mg_l.notna() & (hs.date >= '2008-01-01')]
daily = data.daily_measures()
sonde = daily[daily.measure == list(data.MEASURES)[1]]
SONDE, CITY = "Dredgers' sonde", 'City Harbor Survey'
both = pd.concat([
    sonde.assign(source=SONDE, station='all sites')[['date', 'value', 'source', 'station']],
    hs.assign(source=CITY, value=hs.do_mg_l)[['date', 'value', 'source', 'station']],
], ignore_index=True)
if len(both):
    colors = charts.series()
    dots = alt.Chart(both).mark_circle(size=40, opacity=0.65).encode(
        x=alt.X('date:T', title=None),
        y=alt.Y('value:Q', title='Dissolved oxygen near the surface (mg/L)'),
        color=alt.Color('source:N', title=None, legend=alt.Legend(orient='top', labelLimit=0),
                        scale=alt.Scale(domain=[SONDE, CITY], range=[colors[0], colors[charts.CITY_SURVEY]])),
        tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), 'source:N', 'station:N',
                 alt.Tooltip('value:Q', title='mg/L', format='.2f')],
    )
    std_line = charts.threshold_rule(data.DO_STANDARD_MG_L, f'{data.DO_STANDARD_MG_L:g} mg/L standard')
    st.altair_chart(dots + std_line, width='stretch')
    same = (sonde.set_index('date').value.rename('sonde')
            .to_frame().join(hs.groupby('date').do_mg_l.mean().rename('city'), how='inner'))
    note = (f'On the {len(same)} days both measured, the sonde averaged {same.sonde.mean():.1f} mg/L '
            f'and the city survey {same.city.mean():.1f} mg/L. ' if len(same) else '')
    st.caption(f'{note}Of the city samples shown, {(hs.do_mg_l < data.DO_STANDARD_MG_L).mean():.0%} were '
               f'below {data.DO_STANDARD_MG_L:g} mg/L. The city samples at five canal stations, from Butler '
               'St to the mouth, in the daytime; it also measures near the bottom, not shown here. '
               'Source: NYC DEP Harbor Survey, NYC Open Data.')
    with st.expander('The numbers, by year'):
        by_year = hs.groupby('year').agg(samples=('do_mg_l', 'size'), mean_do=('do_mg_l', 'mean'),
                                         below=('do_mg_l', lambda v: (v < data.DO_STANDARD_MG_L).mean()))
        st.dataframe(by_year.reset_index(), hide_index=True, column_config={
            'year': st.column_config.NumberColumn('Year', format='%d'),
            'samples': 'City samples',
            'mean_do': st.column_config.NumberColumn('Average (mg/L)', format='%.1f'),
            'below': st.column_config.NumberColumn(f'Share below {data.DO_STANDARD_MG_L:g}', format='percent'),
        })
