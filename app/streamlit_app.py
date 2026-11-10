"""
Gowanus Dredgers water data: the Streamlit app's entry point.

Run from the repo root:

    streamlit run app/streamlit_app.py

This file decides who the viewer is and which pages they get. The rules
themselves live in access.py; the pages live in app_pages/. (Not pages/:
Streamlit auto-registers a folder by that name, which would bypass the
access check.)
"""

import pathlib as pl

import streamlit as st

import access
import data

# The Dredgers' logo, from gowanusdredgers.org. Used as the browser-tab icon
# and in the top-left corner (linking back to the Dredgers' site).
LOGO = pl.Path(__file__).parent / 'assets' / 'dredgers_logo.svg'

st.set_page_config(page_title='Gowanus Dredgers water data', page_icon=str(LOGO),
                   layout='wide', initial_sidebar_state='expanded')
st.logo(str(LOGO), size='large', link='https://gowanusdredgers.org')

# Keep the sidebar (the page list) open: hide its collapse button on screens
# wide enough to show it beside the page. Phones keep the button, since there
# the sidebar covers the page and has to be closable.
st.markdown('''<style>
@media (min-width: 768px) {
    [data-testid="stSidebarCollapseButton"] { display: none; }
}
</style>''', unsafe_allow_html=True)

PAGES = {
    'about': st.Page('app_pages/about.py', title='About', default=True),
    'bacteria': st.Page('app_pages/bacteria.py', title='Bacteria'),
    'oxygen': st.Page('app_pages/oxygen.py', title='Dissolved oxygen'),
    'turbidity': st.Page('app_pages/turbidity.py', title='Turbidity'),
    'explore': st.Page('app_pages/explore.py', title='Explore the data'),
    'viewers': st.Page('app_pages/viewers.py', title='Who can see this'),
    # Fixed URL (/privacy): it is the privacy policy link on Google's sign-in screen.
    'privacy': st.Page('app_pages/privacy.py', title='Privacy', url_path='privacy'),
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
