"""Cleaning rules of the loaders added 2026-11-11: sites, advisories, harbor survey.

No database or network: the database modules are stubbed, and each test
feeds the loader's clean() a few hand-made source rows.

    pytest tests/
"""

import pathlib as pl
import sys
import types

import pandas as pd

sys.path.insert(0, str(pl.Path(__file__).parent.parent / 'data_import'))
for name in ('write_to_db', 'apply_schema'):          # never touch the database here
    sys.modules.setdefault(name, types.ModuleType(name))

import advisories  # noqa: E402
import harbor_survey  # noqa: E402
import sites  # noqa: E402


def test_sites_csv_is_well_formed():
    df = sites.read_sites()
    assert not df.site.duplicated().any()
    assert set(df.kind) <= {'sampling site', 'turbidity buoy', 'harbor survey station', 'cso outfall'}
    placed = df.dropna(subset=['lat', 'lon'])
    assert placed.lat.between(40.65, 40.69).all() and placed.lon.between(-74.02, -73.98).all()
    assert len(sites.site_boxes()) == 22                 # the Duro boxes duro.py names readings by
    assert df.loc[df.site == 'Carroll_St', 'lat'].item() == (40.677811 + 40.678560) / 2


def test_advisories_clean():
    raw = pd.DataFrame({
        'Date': ['2024-05-05', '2024-05-05', '', '2024-06-01', ''],
        'Site': ['GOWANUS CANAL, INNER', 'GOWANUS CANAL, OUTER', 'GOWANUS CANAL, INNER',
                 'GOWANUS CANAL, OUTER', ''],
        'Time': ['Server Date and Time: May 5, 2024 5:24:48 PM ', '',
                 'Server Date and Time: Jul 15, 2025 11:31:59 AM', '', 'System date: Aug 18, 2026'],
        'Advisory': ['Yes ', 'NA', 'YES', '', ''],
        'Advisory Info': ['GOWANUS CANAL, INNER  on advisory until 5/6/2024, 12:00:00 AM   RH',
                          'GOWANUS CANAL, OUTER has no advisory', '7/15/2025, 6:00 PM', '', ''],
        'Email?': ['Yes', '', 'No', '', ''],
        'Notes': ['Rained', '', '', '', ''],
        'Flushing Tunnel Status': ['', '', '', '50', ''],
    })
    df = advisories.clean(raw).set_index('sheet_row')
    assert list(df.index) == [2, 3, 4, 5]                       # the footer row (no area) is dropped
    assert list(df.area) == ['inner', 'outer', 'inner', 'outer']
    assert list(df.on_advisory) == [True, False, True, None]
    assert df.advisory_until[2] == pd.Timestamp('2024-05-06 00:00')
    assert df.advisory_until[3] is None                          # "has no advisory" text is not an end time
    assert df.advisory_until[4] == pd.Timestamp('2025-07-15 18:00')
    assert df.rain_gauge[2] == 'RH'
    assert str(df.check_date[4]) == '2025-07-15'                 # date taken from the check when blank
    assert df.emailed[2] is True and df.emailed[4] is False and df.emailed[3] is None


def test_harbor_survey_clean():
    cols = list(harbor_survey.COLUMN_MAP)
    raw = pd.DataFrame([dict.fromkeys(cols)] * 3)
    raw[':id'] = ['a', 'b', 'c']
    raw['sampling_location'] = ['GC3', 'G2', 'GC6']
    raw['sample_date'] = ['2016-01-19T00:00:00.000'] * 3
    raw['sample_time'] = ['9:55', '1:53 PM', '#VALUE!']
    raw['weather_condition_dry_or_wet'] = ['Dry', 'W', None]
    raw['top_enterococci_bacteria_cells_100ml'] = ['1,200', '<10', 'QD']
    raw['lat'] = ['-73.98824', '-74.00333', '-74']
    raw['long'] = ['40.67943', '40.66667', '41']
    df = harbor_survey.clean(raw).set_index('obs_id')
    assert list(df.top_enterococci) == [1200, 10, None]
    assert list(df.weather) == ['dry', 'wet', None]
    assert str(df.sample_time['a']) == '09:55:00' and str(df.sample_time['b']) == '13:53:00'
    assert df.sample_time['c'] is None
    assert (df.lat['a'], df.lon['a']) == (40.67943, -73.98824)   # swapped columns put right
    assert df.lat['c'] is None                                   # 41/-74 placeholder dropped
