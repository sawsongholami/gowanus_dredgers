"""The swim standards: New York State's 104 single-sample and 35 geometric-mean
lines, and CWQT's good / advisory / poor rating built on them.

    pytest tests/
"""

import pathlib as pl
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(pl.Path(__file__).parent.parent / 'app'))

import data  # noqa: E402


def test_standards():
    assert data.SWIM_THRESHOLD_MPN == 104
    assert data.GEO_MEAN_STANDARD_MPN == 35


@pytest.mark.parametrize('geo_mean, expected', [
    (10, 'good'), (35, 'good'),            # "35 or less" is good
    (35.1, 'advisory'), (104, 'advisory'),  # 104 itself is still advisory
    (104.1, 'poor'), (5000, 'poor'),
    (float('nan'), None),
])
def test_rating_band_edges(geo_mean, expected):
    assert data.rating(geo_mean) == expected


def test_static_page_reads_the_shared_standards():
    """The static page's build script imports the one copy in app/standards.py."""
    build = (pl.Path(__file__).parent.parent / 'dashboard' / 'build_data.py').read_text()
    assert 'from standards import' in build
    assert 'SWIM_THRESHOLD_MPN =' not in build


def test_rolling_geo_mean_needs_five_samples_in_30_days():
    weeks = pd.to_datetime(['2024-06-06', '2024-06-13', '2024-06-20', '2024-06-27', '2024-07-04',
                            '2024-07-25'])
    df = pd.DataFrame({'site': 'Second St', 'date': weeks, 'mpn': [10, 10, 10, 10, 1000, 10]})
    r = data.rolling_geo_mean(df).set_index('date')
    # Four weekly samples aren't enough; the fifth week completes a window.
    assert list(r.n.iloc[:5]) == [1, 2, 3, 4, 5]
    assert not r.qualifies.iloc[3] and r.qualifies.iloc[4]
    assert r.geo_mean.iloc[4] == pytest.approx(10 ** 1.4)      # (1+1+1+1+3)/5 decades: 25 MPN
    assert r.rating.iloc[4] == 'good'
    # After a three-week gap the window holds only three samples again.
    assert r.n.iloc[5] == 3 and pd.isna(r.rating.iloc[5])


def test_rolling_geo_mean_keeps_sites_apart():
    d = pd.to_datetime(['2024-06-06'] * 2)
    r = data.rolling_geo_mean(pd.DataFrame({'site': ['A', 'B'], 'date': d, 'mpn': [10, 1000]}))
    assert sorted(r.geo_mean.round().tolist()) == [10, 1000]
