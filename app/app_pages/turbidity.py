"""Weekly turbidity through the two dredging eras."""

import altair as alt
import streamlit as st

import access
import charts
import data
import sections
import site_map

access.require('turbidity')

st.title('How much does dredging cloud the water?')
st.markdown("""
The Superfund cleanup is digging a century of polluted mud off the canal
floor. Digging stirs that mud into the water, so the cleanup team measures
**turbidity**, how cloudy the water is, every 15 minutes. The unit is NTU;
clear drinking water is under 1.

The cleanup works down the canal in stretches. **RTA1** is the top of the
canal, Butler St to 3rd St (dredged 2020 to 2024). **RTA2** is the middle,
3rd St to Hamilton Ave (under way since 2024).
""")

sections.heading('How cloudy was the water, week by week?')
st.markdown('**Weekly turbidity through the two dredging phases.** Each point is one week. '
            'Switch to the 90th percentile to see the spikes: the cloudiest tenth of each week.')

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
site_map.show({'RTA1 stretch': site_map.ZONES['RTA1'], 'RTA2 stretch': site_map.ZONES['RTA2']},
              label='Map: the two stretches of canal and the buoys charted',
              buoys={'RTA1 ambient buoy': 'RTA1 stretch', 'RTA2 ambient buoy': 'RTA2 stretch'},
              note='Small dots are monitoring sites inside each stretch, to show where it is. The '
                   'large dots are the two ambient buoys charted above, placed from where the '
                   "cleanup's weekly reports describe them: during RTA1 in the eastern end of the "
                   'Fourth St Turning Basin, and during RTA2 between Union St and Carroll St bridges, '
                   'mostly just north of Carroll St Bridge (it was moved a few times there).')

st.caption('RTA1 and RTA2 are different stretches of the canal, monitored one after the other with '
           'different buoys, so they are kept as two lines. Only the "ambient" station, which both '
           'have, is shown. RTA2 is measured on weekday daytime shifts only; RTA1 ran around the '
           'clock. Some early readings of exactly 0 NTU are likely instrument setup and are shown '
           'as recorded.')
