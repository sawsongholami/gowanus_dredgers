"""Dissolved oxygen by site, from the Duro sonde."""

import altair as alt
import streamlit as st

import access
import charts
import data
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

st.subheader('Which parts of the canal have enough oxygen?')
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

st.subheader('How bad does it get on a bad day?')
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
