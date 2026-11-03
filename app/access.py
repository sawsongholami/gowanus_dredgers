"""
Who may see what: the one place access is decided.

Three levels, lowest first:

    public  anyone, signed in or not
    team    a signed-in Google account listed in app_viewers as 'team'
    admin   listed in app_viewers as 'admin'

PAGE_ACCESS sets the lowest level allowed to open each page. The entry point
hands st.navigation only the pages the viewer clears, so a page they can't
see has no URL to visit. Each page also calls require() as a second check,
in case a future edit registers a page by mistake.

Everything fails closed: a page missing from PAGE_ACCESS, an unknown role,
an unverified email or an unreachable viewer list all mean 'public'.

Nothing beyond the About and Privacy pages, which hold no data, is public yet. The Duro readings are the
Dredgers' own unpublished data and the CWQT figures belong to another
organisation, so publishing even aggregates is Corinne's call (README,
"Operating notes"). To publish a page once she agrees, set it to 'public'.
"""

import streamlit as st

LEVELS = ('public', 'team', 'admin')

PAGE_ACCESS = {
    'about': 'public',
    'privacy': 'public',   # no data; Google sign-in needs a public privacy policy link
    'bacteria': 'team',
    'oxygen': 'team',
    'turbidity': 'team',
    'viewers': 'admin',
}


def _rank(level):
    return LEVELS.index(level) if level in LEVELS else 0


def can_view(level, page):
    """Unlisted pages need a level above admin, i.e. nobody gets them."""
    required = PAGE_ACCESS.get(page)
    if required is None:
        return False
    return _rank(level) >= _rank(required)


def current_email():
    """The signed-in viewer's email, or None. Only Google-verified emails count."""
    if not st.user.get('is_logged_in', False):
        return None
    if not st.user.get('email_verified', False):
        return None
    email = st.user.get('email')
    return email.strip().lower() if email else None


def viewer_level(email, lookup_role):
    """lookup_role(email) returns the app_viewers role, or None if unlisted."""
    if not email:
        return 'public'
    role = lookup_role(email)
    return role if role in LEVELS[1:] else 'public'


def require(page):
    """Second check at the top of every page: stop unless the viewer clears it."""
    if not can_view(st.session_state.get('viewer_level', 'public'), page):
        st.error('You do not have access to this page.')
        st.stop()
