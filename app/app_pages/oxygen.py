"""Dissolved oxygen by site, from the Duro sonde."""

import altair as alt
import streamlit as st

import access
import charts
import data

access.require('oxygen')

st.title('Dissolved oxygen')
st.markdown(f"""
Fish need oxygen dissolved in the water. New York State's standard for this
class of water is **{data.DO_STANDARD_MG_L:g} mg/L**; below it, fish and other
animals start to struggle.
""")

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
           'Every reading is from a daytime outing of about 40 minutes, so the overnight low, '
           "when oxygen is usually lowest, hasn't been measured.")

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
