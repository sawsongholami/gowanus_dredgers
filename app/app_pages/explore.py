"""Data explorer: put any of the datasets side by side over time, or against each other."""

import altair as alt
import pandas as pd
import streamlit as st

import access
import charts
import data
import sections
import site_map

access.require('explore')

st.title('Explore the data')
st.markdown("""
Pick any of the datasets and see them side by side. Each one is boiled down
to **one number per day for the whole canal**, so they can share a
timeline. They were collected by different people on different schedules,
so they don't always overlap: the table under the chart shows when each one
has data.
""")

df = data.daily_measures()
available = [m for m in data.MEASURES if m in set(df.measure)]
picked = st.multiselect('Datasets', available, default=available[:1] + available[5:6],
                        help='Each dataset gets its own chart, stacked on one timeline.')
if not picked:
    st.info('Pick at least one dataset.')
    st.stop()

sel = df[df.measure.isin(picked)]
first_year, last_year = int(sel.date.dt.year.min()), int(sel.date.dt.year.max())
if first_year < last_year:
    start, end = st.slider('Years', first_year, last_year, (first_year, last_year))
    sel = sel[sel.date.dt.year.between(start, end)]
else:
    start = end = first_year

# --- Side by side over time ---------------------------------------------------
sections.heading('Side by side over time')
st.caption('Drag a chart sideways to pan; the charts move together. Narrow the Years slider to zoom in. '
           'Gaps are days with no measurement, not zeros.')


def over_time(measure):
    spec = data.MEASURES[measure]
    base = alt.Chart(sel[sel.measure == measure])
    color = charts.series()[0]
    mark = {'bar': base.mark_bar(color=color),
            'line': base.mark_line(color=color, strokeWidth=1),
            'point': base.mark_circle(color=color, size=28, opacity=0.6)}[spec['mark']]
    return mark.encode(
        x=alt.X('date:T', title=None,
                scale=alt.Scale(domain=[f'{start}-01-01', f'{end}-12-31'])),
        y=alt.Y('value:Q', title=measure, scale=alt.Scale(type='log' if spec['log'] else 'linear', zero=spec['mark'] == 'bar')),
        tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), alt.Tooltip('value:Q', title=measure, format=',')],
    ).properties(height=170)


# Stacked charts on one shared date axis, each with its own units: the
# honest alternative to two different y-axes on one chart.
# Pan only: wheel-zoom would hijack scrolling down the page.
zoom = alt.selection_interval(bind='scales', encodings=['x'], zoom=False)
stack = alt.vconcat(*[over_time(m).add_params(zoom) for m in picked]).resolve_scale(x='shared')
st.altair_chart(stack, width='stretch')

coverage = sel.groupby('measure').agg(first=('date', 'min'), last=('date', 'max'),
                                      days=('date', 'nunique')).reindex(picked).reset_index()
coverage['what'] = coverage.measure.map(lambda m: data.MEASURES[m]['what'])
st.dataframe(coverage, hide_index=True, column_config={
    'measure': 'Dataset',
    'first': st.column_config.DateColumn('First day', format='YYYY-MM-DD'),
    'last': st.column_config.DateColumn('Last day', format='YYYY-MM-DD'),
    'days': st.column_config.NumberColumn('Days with data', format='%d'),
    'what': 'What the daily number is',
})

# --- Against each other ---------------------------------------------------------
if len(picked) >= 2:
    sections.heading('Against each other')
    st.markdown('Each dot is one day when **both** datasets have a value. A pattern here is a '
                'hint worth checking, not proof that one causes the other.')
    c1, c2 = st.columns(2)
    x_name = c1.selectbox('Across', picked, index=1)
    y_name = c2.selectbox('Up', picked, index=0)
    if x_name == y_name:
        st.info('Pick two different datasets.')
    else:
        wide = sel.pivot(index='date', columns='measure', values='value')
        pair = wide[[x_name, y_name]].dropna().reset_index()
        pair.columns = ['date', 'x', 'y']
        if len(pair) < 3:
            st.info(f'These two datasets share only {len(pair)} day(s) in these years, '
                    'too few to chart. They were collected on different schedules.')
        else:
            def axis(field, name):
                kind = 'log' if data.MEASURES[name]['log'] else 'linear'
                return dict(shorthand=f'{field}:Q', title=name, scale=alt.Scale(type=kind, zero=False))
            dots = alt.Chart(pair).mark_circle(size=40, opacity=0.5, color=charts.series()[0]).encode(
                x=alt.X(**axis('x', x_name)), y=alt.Y(**axis('y', y_name)),
                tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'),
                         alt.Tooltip('x:Q', title=x_name, format=','),
                         alt.Tooltip('y:Q', title=y_name, format=',')],
            )
            st.altair_chart(dots, width='stretch')
            st.caption(f'{len(pair):,} days have both, out of {wide[x_name].notna().sum():,} with '
                       f'{x_name} and {wide[y_name].notna().sum():,} with {y_name}.')

site_map.show({'Monitoring sites': list(site_map.SITES)}, label='Map: the monitoring sites',
              note='The daily numbers on this page combine every site into one value for the canal.')

if len(available) < len(data.MEASURES):
    st.caption('Tide predictions are not available here yet.')
st.caption('Things to know: the sonde readings (oxygen, water temperature, salinity) come from '
           'short daytime outings, August 2023 to October 2024. Turbidity before April 2024 is '
           'the upper canal (RTA1) and after August 2024 the middle canal (RTA2). Rain and air '
           'temperature come from a weather model for a spot about 4.5 km inland, so a local '
           'downpour can be missed.')
