"""
The build step that swaps Streamlit's tab icon for the Dredgers' one
(app/install_tab_icon.py). Fails if a Streamlit upgrade moves the file the
step replaces, so the break shows up here rather than as a wrong icon.
"""

import pathlib as pl
import shutil
import sys

import pytest

sys.path.insert(0, str(pl.Path(__file__).parent.parent / 'app'))

import install_tab_icon  # noqa: E402


def test_streamlit_still_links_its_icon_where_we_expect():
    assert (install_tab_icon.STATIC / 'favicon.png').is_file()
    assert './favicon.png' in (install_tab_icon.STATIC / 'index.html').read_text()


def test_install_replaces_the_icon(tmp_path):
    # A copy of Streamlit's static folder, so the test doesn't touch the real one.
    for name in ('favicon.png', 'index.html'):
        shutil.copy(install_tab_icon.STATIC / name, tmp_path / name)
    target = install_tab_icon.install(static_dir=tmp_path)
    assert target.read_bytes() == install_tab_icon.ICON.read_bytes()


def test_install_fails_loudly_if_the_icon_moved(tmp_path):
    (tmp_path / 'index.html').write_text('<html></html>')
    with pytest.raises(SystemExit):
        install_tab_icon.install(static_dir=tmp_path)
