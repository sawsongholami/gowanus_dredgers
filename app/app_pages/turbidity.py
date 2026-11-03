"""Weekly turbidity through the two dredging eras."""

import altair as alt
import streamlit as st

import access
import charts
import data

access.require('turbidity')

st.title('Turbidity')
st.markdown("""
Turbidity is how cloudy the water is, measured in NTU. Dredging stirs up
sediment, so the Superfund cleanup monitors it every 15 minutes.
""")

df = data.turbidity_weekly()
stat = st.segmented_control(
    'Show', ['Weekly median', 'Weekly 90th percentile'], default='Weekly median',
    help='The median is the typical week; the 90th percentile shows the spikes.') or 'Weekly median'
field = 'p90_ntu' if stat == 'Weekly 90th percentile' else 'median_ntu'

lines = alt.Chart(df).mark_line(strokeWidth=2).encode(
    x=alt.X('week:T', title=None),
    y=alt.Y(f'{field}:Q', title=f'{stat} (NTU)'),
    color=alt.Color('phase:N', title='Cleanup phase',
                    scale=alt.Scale(domain=['RTA1', 'RTA2'], range=charts.series()),
                    legend=alt.Legend(orient='top')),
    tooltip=[alt.Tooltip('week:T', title='week of', format='%Y-%m-%d'), 'phase:N',
             alt.Tooltip('median_ntu:Q', title='median (NTU)'),
             alt.Tooltip('p90_ntu:Q', title='90th percentile (NTU)'),
             alt.Tooltip('n:Q', title='readings', format=',')],
)
st.altair_chart(lines, width='stretch')

st.caption('RTA1 and RTA2 are different stretches of the canal, monitored one after the other with '
           'different buoys, so they are kept as two lines. Only the "ambient" station, which both '
           'have, is shown. RTA2 is measured on weekday daytime shifts only; RTA1 ran around the '
           'clock. Some early readings of exactly 0 NTU are likely instrument setup and are shown '
           'as recorded.')
