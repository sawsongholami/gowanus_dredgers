"""The canal map that opens from each section, showing where a figure's data comes from.

Site locations come from db/sites.csv, the project's one list of sites (see
data_import/sites.py). The map reads the file, not the database, so the
public About page's map makes no database query.
"""

import importlib.util
import pathlib as pl

import pandas as pd
import pydeck as pdk
import streamlit as st

import charts

# Load data_import/sites.py by path: it needs only pandas, and importing it
# this way keeps the other loaders' modules off the app's import path.
_spec = importlib.util.spec_from_file_location(
    'gd_sites', pl.Path(__file__).parent.parent / 'data_import' / 'sites.py')
_sites = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sites)


def _name(slug):
    return slug.replace('_', ' ')   # display form, as on the pages: 'Second St'


_ALL = _sites.read_sites()
_placed = _ALL.dropna(subset=['lat', 'lon'])
_monitoring = _placed[_placed.kind == 'sampling site']
_buoys = _placed[_placed.kind == 'turbidity buoy']

# Centre (or pin) of each placed sampling site, north to south as in the CSV.
SITES = {_name(r.site): (r.lat, r.lon) for r in _monitoring.itertuples()}
# EPA cleanup zone of each site.
ZONES = {z: [_name(s) for s in g.site] for z, g in _ALL[_ALL.kind == 'sampling site'].groupby('rta_zone')}
# Turbidity buoys, placed approximately from the cleanup's weekly reports.
BUOYS = {_name(r.site): (r.lat, r.lon) for r in _buoys.itertuples()}

_OTHER = [138, 137, 132, 110]   # sites this figure doesn't use: recessive gray


def _rgb(hex_color):
    return [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]


def show(groups, note=None, label='Map: where this was measured', expanded=False, buoys=None):
    """An expander holding the canal map, with this figure's sites picked out.

    groups: {legend label: [site names]}. Each group gets a series color, in
    order, so a map can match its chart's lines. Every other site is a small
    gray dot. Site names are the display form ('Second St'), as on the pages.
    buoys: {name in BUOYS: group label}, drawn as larger ringed markers in
    that group's color.
    """
    colors = charts.series()
    rows, unplaced, legend = [], [], []
    used = set()
    for i, (group, sites) in enumerate(groups.items()):
        color = colors[i % len(colors)]
        legend.append(f'<span style="color:{color}">&#9679;</span> {group}')
        for site in sites:
            if site not in SITES:
                unplaced.append(site)
                continue
            used.add(site)
            rows.append({'site': site, 'group': group, 'lat': SITES[site][0], 'lon': SITES[site][1],
                         'color': _rgb(color) + [230], 'radius': 26})
    for site, (lat, lon) in SITES.items():
        if site not in used:
            rows.append({'site': site, 'group': 'Not part of this figure', 'lat': lat, 'lon': lon,
                         'color': _OTHER, 'radius': 14})
    group_color = {g: colors[i % len(colors)] for i, g in enumerate(groups)}
    for name, group in (buoys or {}).items():
        lat, lon = BUOYS[name]
        rows.append({'site': f'{name} (approximate)', 'group': group, 'lat': lat, 'lon': lon,
                     'color': _rgb(group_color[group]) + [255], 'radius': 45})
    # Gray first, so the highlighted dots draw on top.
    df = pd.DataFrame(rows).sort_values('radius')

    with st.expander(label, expanded=expanded):
        st.pydeck_chart(pdk.Deck(
            initial_view_state=pdk.ViewState(latitude=40.6742, longitude=-73.9948, zoom=14),
            layers=[pdk.Layer('ScatterplotLayer', df, get_position='[lon, lat]', get_fill_color='color',
                              get_radius='radius', radius_min_pixels=3, stroked=True,
                              get_line_color=[255, 255, 255], line_width_min_pixels=1, pickable=True)],
            tooltip={'text': '{site}\n{group}'},
        ), height=380)
        if buoys:
            legend.append('Large dots: the ambient buoy of each stretch (approximate)')
        legend.append(f'<span style="color:{charts.REFERENCE}">&#9679;</span> Other monitoring sites')
        st.caption(' &nbsp; '.join(legend), unsafe_allow_html=True)
        if unplaced:
            st.caption(f"Not on the map yet: {', '.join(sorted(set(unplaced)))} "
                       '(no coordinates on file for these sites).')
        if note:
            st.caption(note)
