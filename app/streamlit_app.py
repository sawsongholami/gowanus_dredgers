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
import sections

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
/* Bigger corner logo than st.logo allows (it stops at 32px). If a Streamlit
   update renames these, the logo just falls back to its small size. */
[data-testid="stSidebarHeader"] { height: auto; padding-bottom: 0.5rem; }
[data-testid="stLogoLink"] { height: auto; }
[data-testid="stSidebarLogo"] { height: 6rem; }
/* Sidebar menu: tight list of page links; the open page and its section
   links share one highlighted box. */
.st-key-menu { gap: 0.125rem; }
.st-key-menu_current {
    gap: 0; padding-bottom: 0.5rem; border-radius: 0.5rem;
    background-color: rgba(151, 166, 195, 0.25);
}
.st-key-menu_current [data-testid="stPageLink-NavLink"] { background: transparent; }
.st-key-menu_current [data-testid="stPageLink-NavLink"] p { font-weight: 600; }
/* The section list (stMarkdown, not the page link's own label): bulleted,
   indented past the page name, a size smaller. */
.st-key-menu_current [data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] { margin-bottom: 0; }
.st-key-menu_current [data-testid="stMarkdown"] ul { margin: 0; padding-left: 2rem; }
.st-key-menu_current [data-testid="stMarkdown"] li {
    margin: 0 0.5rem 0.35rem 0; padding: 0; font-size: 0.8rem; line-height: 1.35;
}
.st-key-menu_current [data-testid="stMarkdown"] li::marker { color: rgba(151, 166, 195, 0.9); }
.st-key-menu_current [data-testid="stMarkdown"] a { color: inherit; text-decoration: none; }
.st-key-menu_current [data-testid="stMarkdown"] a:hover { text-decoration: underline; }
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

visible = [page for key, page in PAGES.items() if access.can_view(level, key)]
# Streamlit's own page list can't show a page's sections, so it's hidden and
# the sidebar menu below is drawn by hand: one link per page, and under the
# open page, links to its sections, all in one highlighted box.
current = st.navigation(visible, position='hidden')

with st.sidebar:
    menu = st.container(key='menu')
    if st.user.get('is_logged_in', False):
        st.caption(f"Signed in as {st.user.get('email')}")
        if level == 'public':
            st.info("This account isn't on the viewer list yet. Ask the project team to add it.")
        st.button('Sign out', on_click=st.logout)
    else:
        st.button('Sign in with Google', on_click=st.login, type='primary')


def draw_menu():
    """Page links, with the open page's sections listed in its box.

    Runs after the page, since the page's headings are only known once it
    has drawn them.
    """
    with menu:
        for page in visible:
            if page.url_path != current.url_path:
                st.page_link(page)
                continue
            with st.container(key='menu_current'):
                st.page_link(page)
                links = [f'- [{title}](#{sections.slug(title)})' for title in sections.collected()]
                if links:
                    st.markdown('\n'.join(links))


sections.reset()
try:
    current.run()
finally:
    # Also when the page stops early (st.stop) or fails, so the menu is never missing.
    draw_menu()
