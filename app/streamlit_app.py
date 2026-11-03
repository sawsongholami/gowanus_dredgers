"""
Gowanus Dredgers water data: the Streamlit app's entry point.

Run from the repo root:

    streamlit run app/streamlit_app.py

This file decides who the viewer is and which pages they get. The rules
themselves live in access.py; the pages live in app_pages/. (Not pages/:
Streamlit auto-registers a folder by that name, which would bypass the
access check.)
"""

import streamlit as st

import access
import data

st.set_page_config(page_title='Gowanus Dredgers water data', page_icon='🌊', layout='wide')

PAGES = {
    'about': st.Page('app_pages/about.py', title='About', icon='🏠', default=True),
    'bacteria': st.Page('app_pages/bacteria.py', title='Bacteria', icon='🦠'),
    'oxygen': st.Page('app_pages/oxygen.py', title='Dissolved oxygen', icon='🐟'),
    'turbidity': st.Page('app_pages/turbidity.py', title='Turbidity', icon='🌫️'),
    'viewers': st.Page('app_pages/viewers.py', title='Who can see this', icon='🔑'),
}

email = access.current_email()
try:
    level = access.viewer_level(email, data.viewer_role)
except Exception:
    # Viewer list unreachable: fail closed, and say so rather than
    # silently showing a signed-in viewer the public view.
    level = 'public'
    if email:
        st.warning("Couldn't check the viewer list just now, so you're seeing the public view. "
                   'Try reloading in a minute.')
st.session_state['viewer_level'] = level

with st.sidebar:
    if st.user.get('is_logged_in', False):
        st.caption(f"Signed in as {st.user.get('email')}")
        if level == 'public':
            st.info("This account isn't on the viewer list yet. Ask the project team to add it.")
        st.button('Sign out', on_click=st.logout)
    else:
        st.button('Sign in with Google', on_click=st.login, type='primary')

nav = st.navigation([page for key, page in PAGES.items() if access.can_view(level, key)])
nav.run()
