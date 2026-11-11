"""
Re-applies the app's read permissions: everything in db/app_reader.sql below
its "safe to re-run" line (GRANTs and row-level-security policies).

Creating the app_reader login itself stays a one-time step in the Supabase
SQL editor, because its password can't live in a file. Run this after giving
the app a new table or view to read:

    python apply_app_grants.py
"""

import pathlib as pl

import write_to_db

SQL_PATH = pl.Path(__file__).parent.parent / 'db' / 'app_reader.sql'
MARKER = '-- Everything below is safe to re-run.'


def statements():
    sql = SQL_PATH.read_text()
    if MARKER not in sql:
        raise RuntimeError(f'{SQL_PATH.name} no longer has the line "{MARKER}"; '
                           'update apply_app_grants.py to match.')
    body = sql.split(MARKER, 1)[1].split('\n', 1)[1]   # drop the rest of the marker's line
    lines = [line.split('--')[0] for line in body.splitlines()]
    return [s.strip() for s in '\n'.join(lines).split(';') if s.strip()]


def apply():
    stmts = statements()
    for statement in stmts:
        write_to_db.run_sql(statement)
    print(f'Applied {len(stmts)} grant and policy statements from {SQL_PATH.name}.')


if __name__ == '__main__':
    apply()
