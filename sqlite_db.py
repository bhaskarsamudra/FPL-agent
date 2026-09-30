"""SQLite database infrastructure for the FPL Strategist.

This module owns SQLite connection setup and schema initialization only.
Business logic and strategy modules should not execute SQL directly.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "fpl_strategist.db"
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"


def connect_sqlite(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with foreign-key enforcement enabled."""
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create the project database and apply the current schema idempotently."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with connect_sqlite(db_path) as connection:
        connection.executescript(schema_sql)
        connection.execute("PRAGMA foreign_keys = ON")


def list_tables(db_path: str | Path = DEFAULT_DB_PATH) -> list[str]:
    """Return application table names in deterministic order."""
    with connect_sqlite(db_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    return [row["name"] for row in rows]
