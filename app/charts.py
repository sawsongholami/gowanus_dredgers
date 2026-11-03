"""Shared chart pieces, so every page draws marks and reference lines alike."""

import altair as alt
import pandas as pd
import streamlit as st

# Categorical slots 1 and 2 of the validated default palette, in fixed order.
# Dark mode uses the same hues stepped for the dark surface, not a flip.
_SERIES = {'light': ['#2a78d6', '#eb6834'], 'dark': ['#3987e5', '#d95926']}
REFERENCE = '#8a8984'   # threshold and standard lines: recessive gray


def series():
    """Series colors for the viewer's current light/dark theme."""
    return _SERIES['dark' if st.context.theme.type == 'dark' else 'light']


def threshold_rule(value, label):
    """A dashed horizontal reference line with its label at the left."""
    df = pd.DataFrame({'y': [value], 'label': [label]})
    rule = alt.Chart(df).mark_rule(color=REFERENCE, strokeDash=[4, 4], strokeWidth=1.5).encode(y='y:Q')
    text = alt.Chart(df).mark_text(align='left', dx=4, dy=-6, color=REFERENCE).encode(
        y='y:Q', x=alt.value(0), text='label:N')
    return rule + text
