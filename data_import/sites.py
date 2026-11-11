"""
The one list of monitoring sites: db/sites.csv, a version-controlled seed
file. Everything that needs site locations reads it:

- this loader copies it into the `sites` table, which the `site_zones` view
  (and through it the daily summaries) joins on;
- duro.py reads the GPS boxes from it to name each sonde reading's site;
- the app's maps read the file directly (app/site_map.py), so public pages
  never query the database.

Edit the CSV, not the code, to add or move a site; then run this (apply_schema
also runs it, so any loader run picks the change up):

    python sites.py

Columns: site (the slug stored in duro/cwqt), kind ('sampling site' or
'turbidity buoy'), rta_zone, the GPS box (lat_min..lon_max) for Duro sites,
or a single lat/lon pin for the rest, source and note. A site with neither
a box nor a pin is known but not yet placed.
"""

import pathlib as pl

import pandas as pd
from sqlalchemy import text

SITES_CSV = pl.Path(__file__).parent.parent / 'db' / 'sites.csv'
BOX = ['lat_min', 'lat_max', 'lon_min', 'lon_max']


def read_sites(path=SITES_CSV) -> pd.DataFrame:
    """The seed file, with lat/lon filled in as the box centre where a site
    has a box rather than a pin."""
    df = pd.read_csv(path, dtype={'site': str, 'kind': str, 'rta_zone': str, 'source': str, 'note': str})
    has_box = df[BOX].notna().all(axis=1)
    df.loc[has_box, 'lat'] = (df.lat_min + df.lat_max)[has_box] / 2
    df.loc[has_box, 'lon'] = (df.lon_min + df.lon_max)[has_box] / 2
    if df.site.duplicated().any():
        raise ValueError(f'duplicate sites in {path.name}: {sorted(df.site[df.site.duplicated()])}')
    return df


def site_boxes() -> list[tuple]:
    """(site, lat_min, lat_max, lon_min, lon_max) for every site with a GPS box."""
    df = read_sites().dropna(subset=BOX)
    return list(df[['site', *BOX]].itertuples(index=False, name=None))


def main():
    import write_to_db
    df = read_sites()
    # Small reference table: replace it whole, in one transaction, so a site
    # removed from the CSV leaves the table too.
    with write_to_db.get_engine().begin() as conn:
        conn.execute(text('DELETE FROM sites'))
        df.to_sql('sites', conn, if_exists='append', index=False)
    print(f'sites: {len(df)} rows from {SITES_CSV.name}')


if __name__ == '__main__':
    main()
