"""
Applies db/schema.sql to the Supabase database.

Every statement in schema.sql is idempotent, so running this repeatedly is
safe. Loaders call apply() before writing, so the schema is always current;
run it directly after editing schema.sql to push a change on its own:

    python apply_schema.py
"""

import pathlib as pl

import write_to_db

SCHEMA_PATH = pl.Path(__file__).parent.parent / 'db' / 'schema.sql'


def apply():
    sql = SCHEMA_PATH.read_text()
    # Strip `--` comments so semicolons inside them don't split statements.
    # (No support for string literals containing '--' or ';'; keep
    # schema.sql to plain DDL.)
    lines = [line.split('--')[0] for line in sql.splitlines()]
    statements = [s.strip() for s in '\n'.join(lines).split(';') if s.strip()]
    for statement in statements:
        write_to_db.run_sql(statement)
    print(f'Applied {len(statements)} statements from {SCHEMA_PATH.name}.')


if __name__ == '__main__':
    apply()
