"""
Page sections: headings that also show up as links in the sidebar menu.

A page calls heading('...') instead of st.header / st.subheader. That draws
the heading with a fixed anchor and records it, so streamlit_app.py can list
the open page's sections under its name in the sidebar after the page runs.
The page itself is the one place a heading is written, so the menu can't
drift out of step with it.
"""

import re

import streamlit as st

_KEY = '_page_sections'


def slug(title: str) -> str:
    """'Where is it worst?' -> 'where-is-it-worst'."""
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')


def reset():
    st.session_state[_KEY] = []


def heading(title: str, level: str = 'subheader'):
    """Draws a section heading (level 'header' or 'subheader') and records it."""
    getattr(st, level)(title, anchor=slug(title))
    st.session_state.setdefault(_KEY, []).append(title)


def collected() -> list[str]:
    return st.session_state.get(_KEY, [])
