"""
db.py -- SQLite connection + upsert helpers for the Commodity & Macro
Intelligence Dashboard.

Usage:
    from db import init_db, upsert_dataframe

    conn = init_db()                       # creates commodity_dashboard.db
    upsert_dataframe(conn, "raw_prices", df)
    conn.close()
"""

import sqlite3
import os

DB_PATH = "commodity_dashboard.db"
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def init_db(db_path=DB_PATH, schema_path=SCHEMA_PATH):
    """Connect to (creating if needed) the SQLite file and ensure all
    tables from schema.sql exist. Safe to call every run -- CREATE TABLE
    IF NOT EXISTS means it never wipes existing data."""
    conn = sqlite3.connect(db_path)
    with open(schema_path, "r") as f:
        conn.executescript(f.read())
    return conn


def upsert_dataframe(conn, table, df):
    """Insert every row of df into `table`, replacing any existing row
    that collides on the table's primary key (idempotent re-runs).

    df's column names must exactly match the target table's column
    names -- this function doesn't do any renaming or type coercion,
    by design, so a mismatch fails loudly instead of silently inserting
    into the wrong columns.
    """
    if df.empty:
        return 0

    df = df.where(df.notnull(), None)  # NaN -> NULL, not the literal string "nan"

    cols = list(df.columns)
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"

    conn.executemany(sql, df[cols].itertuples(index=False, name=None))
    conn.commit()

    return len(df)


def query(conn, sql, params=None):
    """Convenience wrapper: run a SELECT and get back a DataFrame."""
    import pandas as pd
    return pd.read_sql_query(sql, conn, params=params)