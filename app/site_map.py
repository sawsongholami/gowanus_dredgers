"""The canal map that opens from each section, showing where a figure's data comes from.

SITES is the centre of each site's GPS box. The boxes themselves are defined
in data_import/duro.py (SITE_BOXES, from the Duro Data Dictionary); this is a
copy, because the app can't import the loaders. If a box changes there,
change it here. Two CWQT sites have no box: Lowlands is placed from the
project lead's pin (2026-11-11); Dentons Pond has no place on the map yet (its
outfall is somewhere near Whole Foods; the lead is asking the sampler).
"""

import pandas as pd
import pydeck as pdk
import streamlit as st

import charts

SITES = {
    'Douglass St': (40.681473, -73.987058),
    'Carroll St': (40.678186, -73.989200),
    'First St': (40.677485, -73.989350),
    'Second St': (40.676800, -73.989650),
    'Third St': (40.676150, -73.990190),
    'WholeFoodsWest': (40.675694, -73.990450),
    'Third Ave': (40.674310, -73.989000),
    'Fourth St TB': (40.674864, -73.990060),
    'Second Ave': (40.675369, -73.990748),
    'Bond St': (40.676006, -73.992600),
    'Sixth St TB': (40.674868, -73.992373),
    'Seventh St TB': (40.674514, -73.994175),
    'Seventh St Canal': (40.675142, -73.995575),
    'Huntington St': (40.674768, -73.995890),
    'Ninth St Bridge': (40.674086, -73.996536),
    'South of Ninth St Bridge': (40.673528, -73.996976),
    'Eleventh St TB': (40.672735, -73.997092),
    'Hamilton Bridge': (40.671600, -73.998581),
    'South of Hamilton Bridge': (40.670889, -73.998908),
    'Sanitation TB': (40.669263, -73.998635),
    'GD Bunker': (40.667623, -74.000155),
    'Mouth': (40.667040, -74.002775),
    # CWQT only, no Duro box: a pin from the project lead, not a box centre.
    'Lowlands': (40.674319, -73.996460),
}

# EPA cleanup zone of each site, north to south (db/schema.sql, site_zones).
ZONES = {
    'RTA1': ['Douglass St', 'Carroll St', 'First St', 'Second St', 'Third St', 'Bond St'],
    'RTA2': ['WholeFoodsWest', 'Second Ave', 'Seventh St Canal', 'Sixth St TB', 'Huntington St',
             'Fourth St TB', 'Seventh St TB', 'Third Ave', 'Ninth St Bridge',
             'South of Ninth St Bridge', 'Eleventh St TB', 'Hamilton Bridge'],
    'RTA3': ['South of Hamilton Bridge', 'Sanitation TB', 'GD Bunker', 'Mouth'],
}

# The turbidity buoys charted on the turbidity page, placed from the cleanup's
# weekly reports, which describe positions in words, so these are approximate.
# RTA1 (Aug 2023 - Apr 2024): "the eastern end of TB4" (Fourth St Turning Basin).
# RTA2: between Union St and Carroll St bridges, moved a few times; mostly at or
# about 50-80 ft north of Carroll St Bridge, which is where this puts it.
BUOYS = {
    'RTA1 ambient buoy': (40.67480, -73.98930),
    'RTA2 ambient buoy': (40.67836, -73.98925),
}

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
