"""Shared chart pieces, so every page draws marks and reference lines alike."""

import altair as alt
import pandas as pd
import streamlit as st

# Categorical slots 1-3 of the validated default palette, in fixed order
# (the first three pass the colour-blindness checks as a set). Dark mode uses
# the same hues stepped for the dark surface, not a flip. Slot 3 (aqua) is
# always the city's Harbor Survey; it is low-contrast on white, so charts
# using it carry a legend and a table view.
_SERIES = {'light': ['#2a78d6', '#eb6834', '#1baf7a'], 'dark': ['#3987e5', '#d95926', '#199e70']}
CITY_SURVEY = 2   # index of the Harbor Survey's colour in series()
REFERENCE = '#8a8984'   # threshold and standard lines: recessive gray


def series():
    """Series colors for the viewer's current light/dark theme."""
    return _SERIES['dark' if st.context.theme.type == 'dark' else 'light']


def threshold_rule(value, label, color=REFERENCE):
    """A dashed horizontal reference line with its label at the left. Pass the
    color of the marks it judges when a chart has two standards for two kinds
    of mark."""
    df = pd.DataFrame({'y': [value], 'label': [label]})
    rule = alt.Chart(df).mark_rule(color=color, strokeDash=[4, 4], strokeWidth=1.5).encode(y='y:Q')
    text = alt.Chart(df).mark_text(align='left', dx=4, dy=-6, color=color).encode(
        y='y:Q', x=alt.value(0), text='label:N')
    return rule + text
