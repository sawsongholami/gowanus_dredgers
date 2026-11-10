"""
The Streamlit app's access gate: who gets which pages, and that nobody
below 'team' causes a single data query.

No database or Google login needed: the viewer's email and the viewer list
are stubbed, and every data loader is replaced with one that fails the test
if a page calls it when it shouldn't.

    pip install -r app/requirements.txt pytest
    pytest tests/
"""

import pathlib as pl
import sys

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

APP_DIR = pl.Path(__file__).parent.parent / 'app'
sys.path.insert(0, str(APP_DIR))

import access  # noqa: E402
import data  # noqa: E402

ENTRY = str(APP_DIR / 'streamlit_app.py')
LOADERS = ('enterococcus', 'oxygen_by_site', 'turbidity_weekly', 'daily_measures', 'viewers')
PRIVATE_PAGES = ('bacteria', 'oxygen', 'turbidity', 'explore', 'viewers')


def _fake_frames():
    dates = pd.to_datetime(['2024-06-06', '2024-06-13', '2025-07-10'])
    return {
        'enterococcus': pd.DataFrame({
            'date': dates, 'site': ['Second St', 'Lowlands', 'Second St'],
            'mpn': [10.0, 2400.0, 85.0], 'rain_72h_in': [0.0, 0.8, 0.05],
            'year': dates.year, 'over_threshold': [False, True, False],
            'hours_from_high_tide': [-5.0, 0.5, 4.5]}),
        'daily_measures': pd.DataFrame({
            'date': list(dates) * 2,
            'measure': ['Enterococcus (MPN/100 mL)'] * 3 + ['Rain (mm per day)'] * 3,
            'value': [10.0, 2400.0, 85.0, 0.0, 20.3, 1.2]}),
        'oxygen_by_site': pd.DataFrame({
            'site': ['Second St'], 'rta_zone': ['RTA1'], 'n': [500], 'mean_do': [4.2],
            'p10_do': [2.1], 'pct_below': [60.0],
            'first_day': [pd.Timestamp('2024-06-01')], 'last_day': [pd.Timestamp('2025-08-01')]}),
        'turbidity_weekly': pd.DataFrame({
            'week': pd.to_datetime(['2023-08-07', '2024-09-02']), 'median_ntu': [6.3, 7.1],
            'p90_ntu': [12.0, 15.5], 'n': [600, 200], 'phase': ['RTA1', 'RTA2']}),
        'viewers': pd.DataFrame({'email': ['a@example.com'], 'role': ['admin'],
                                 'note': [None], 'added_at': [pd.Timestamp('2026-11-03')]}),
    }


@pytest.fixture
def viewer(monkeypatch):
    """viewer(email, role, data_allowed) sets who is looking and returns the loader calls."""
    calls = []

    def setup(email, role, data_allowed):
        monkeypatch.setattr(access, 'current_email', lambda: email)
        if isinstance(role, Exception):
            def lookup(_):
                raise role
        else:
            def lookup(_):
                return role
        monkeypatch.setattr(data, 'viewer_role', lookup)
        frames = _fake_frames()
        for name in LOADERS:
            def loader(name=name):
                calls.append(name)
                if not data_allowed:
                    raise AssertionError(f'{name}() was called for a viewer who may not see data')
                return frames[name]
            monkeypatch.setattr(data, name, loader)
        return calls

    return setup


def _run(page=None):
    """Opens the app, then the page; None if the page isn't registered for this viewer.

    An unregistered page has no URL: the real app shows "page not found" and
    AppTest refuses to switch to it, which is what an unreachable page means.
    """
    at = AppTest.from_file(ENTRY, default_timeout=30)
    at.run()
    if page:
        try:
            at.switch_page(f'app_pages/{page}.py')
        except ValueError:
            return None
        at.run()
    return at


def _titles(at):
    return [t.value for t in at.title]


# --- Pure rules -----------------------------------------------------------

def test_unknown_page_and_role_fail_closed():
    assert not access.can_view('admin', 'no_such_page')
    assert access.viewer_level('x@example.com', lambda e: 'superuser') == 'public'
    assert access.viewer_level(None, lambda e: 'admin') == 'public'


def test_only_data_free_pages_are_public_until_corinne_agrees():
    assert [p for p, lvl in access.PAGE_ACCESS.items() if lvl == 'public'] == ['about', 'privacy']


# --- The running app --------------------------------------------------------

@pytest.mark.parametrize('email, role', [
    (None, None),                              # signed out
    ('stranger@example.com', None),            # signed in, not on the list
    ('team@example.com', RuntimeError('db')),  # on the list, but the list is unreachable
])
def test_public_viewers_see_only_about_and_trigger_no_queries(viewer, email, role):
    calls = viewer(email, role, data_allowed=False)
    at = _run()
    assert not at.exception
    assert _titles(at) == ['Gowanus Dredgers Data Dashboard']
    for page in PRIVATE_PAGES:
        assert _run(page) is None, f'{page} was reachable'
    assert _titles(_run('privacy')) == ['Privacy']
    assert calls == []


def test_team_sees_charts_but_not_the_viewer_list(viewer):
    calls = viewer('team@example.com', 'team', data_allowed=True)
    for page, title in [('bacteria', 'Is the canal safe to swim in?'),
                        ('oxygen', 'Can fish survive in the canal?'),
                        ('turbidity', 'How much does dredging cloud the water?'),
                        ('explore', 'Explore the data')]:
        at = _run(page)
        assert not at.exception, at.exception
        assert _titles(at) == [title]
    assert _run('viewers') is None
    assert 'viewers' not in calls


def test_admin_sees_the_viewer_list(viewer):
    viewer('admin@example.com', 'admin', data_allowed=True)
    at = _run('viewers')
    assert not at.exception, at.exception
    assert _titles(at) == ['Who can see this']


def test_geometric_mean_and_one_year_view(viewer):
    assert data.geo_mean([10, 1000]) == pytest.approx(100)
    viewer('team@example.com', 'team', data_allowed=True)
    at = _run('bacteria')
    at.selectbox[0].select('2024').run()
    assert not at.exception, at.exception
