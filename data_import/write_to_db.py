import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Credentials live in the .env file at the repo root (gitignored).
# Copy .env.example to .env and fill in the values from the Supabase dashboard
# (Project Settings > Database > Connection info).
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        host = os.environ.get("SUPABASE_DB_HOST")
        port = os.environ.get("SUPABASE_DB_PORT", "6543")
        user = os.environ.get("SUPABASE_DB_USER")
        password = os.environ.get("SUPABASE_DB_PASSWORD")
        if not all([host, user, password]):
            raise RuntimeError(
                "Missing database credentials. Create a .env file in the repo root "
                "with SUPABASE_DB_HOST, SUPABASE_DB_USER and SUPABASE_DB_PASSWORD "
                "(see .env.example)."
            )
        _engine = create_engine(
            f"postgresql+psycopg2://{user}:{password}@{host}:{port}/postgres"
        )
    return _engine


def run_sql(sql: str):
    """Executes a single SQL statement (e.g. CREATE TABLE IF NOT EXISTS ...)."""
    with get_engine().begin() as conn:
        conn.execute(text(sql))


def write_df_to_table(df: pd.DataFrame, table_name: str, pk_cols: list[str]):
    """
    Writes a DataFrame directly into a Supabase table, upserting on pk_cols.

    Simple inserts (no conflict handling) can just do:
        df.to_sql(table_name, engine, if_exists="append", index=False)

    But since your tables have composite primary keys and scripts may rerun
    on overlapping dates, this uses a staging-table + ON CONFLICT upsert.
    """
    staging_table = f"staging_{table_name}"

    with get_engine().begin() as conn:
        # 1. Dump the DataFrame into a temp staging table.
        #    to_sql infers column types from the DataFrame automatically.
        df.to_sql(staging_table, conn, if_exists="replace", index=False)

        # 2. Build and run the upsert from staging into the real table.
        #    Staged columns are cast to the target table's column types,
        #    since to_sql stores some Python types (e.g. datetime.time)
        #    as text.
        target_types = dict(conn.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = :t AND table_schema = current_schema()
            """),
            {"t": table_name},
        ).fetchall())

        cols = list(df.columns)
        non_pk_cols = [c for c in cols if c not in pk_cols]

        col_list = ", ".join(cols)
        select_list = ", ".join(
            f"CAST({c} AS {target_types[c]})" if c in target_types else c
            for c in cols
        )
        conflict_cols = ", ".join(pk_cols)
        set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_pk_cols)

        upsert_sql = f"""
            INSERT INTO {table_name} ({col_list})
            SELECT {select_list} FROM {staging_table}
            ON CONFLICT ({conflict_cols})
            DO UPDATE SET {set_clause};
        """
        conn.execute(text(upsert_sql))
        conn.execute(text(f"DROP TABLE {staging_table};"))

    print(f"Done. {len(df)} rows upserted into {table_name}.")
    export_table_csv(table_name, pk_cols)


def export_table_csv(table_name: str, order_cols: list[str]):
    """
    Snapshots the table's full current contents to data/exports/<table>.csv
    so there's always a human-browsable copy that matches the database.
    Ordered by primary key so re-exports diff cleanly.
    """
    dir_exports = os.path.join(os.path.dirname(__file__), "..", "data", "exports")
    os.makedirs(dir_exports, exist_ok=True)
    order_by = ", ".join(order_cols)
    full = pd.read_sql(f"SELECT * FROM {table_name} ORDER BY {order_by}",
                       get_engine())
    path = os.path.join(dir_exports, f"{table_name}.csv")
    full.to_csv(path, index=False)
    print(f"Exported {len(full)} rows to data/exports/{table_name}.csv")
