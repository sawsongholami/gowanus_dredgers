"""
Put the Dredgers' icon in place of Streamlit's own browser-tab icon.

Run once after installing the app's requirements (Render's build command):

    pip install -r app/requirements.txt && python app/install_tab_icon.py

Why: the page Streamlit sends first carries its own icon (static/favicon.png,
linked from static/index.html). The app's page_icon only replaces it once
the app has run, so until then, and in browsers like Safari that keep the
first icon they see, the tab shows Streamlit's logo. Swapping the file
fixes the icon from the first moment.

This edits an installed package, which a reinstall or upgrade undoes; the
build reruns it every deploy. If a Streamlit upgrade moves the file, the
script fails the build loudly rather than skip, and the worst case is the
old behaviour: Streamlit's icon until the app loads. tests/test_tab_icon.py
checks the file is still where this expects it.
"""

import pathlib as pl
import shutil
import sys

import streamlit

ICON = pl.Path(__file__).parent / 'assets' / 'dredgers_icon.png'
STATIC = pl.Path(streamlit.__file__).parent / 'static'


def install(static_dir=STATIC, icon=ICON):
    """Copy the icon over static_dir/favicon.png, which index.html must link."""
    target = static_dir / 'favicon.png'
    index = static_dir / 'index.html'
    if not target.is_file() or 'favicon.png' not in index.read_text():
        sys.exit(f"Streamlit's tab icon isn't at {target} any more; update app/install_tab_icon.py.")
    shutil.copyfile(icon, target)
    return target


if __name__ == '__main__':
    print(f'Tab icon installed at {install()}')
