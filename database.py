"""SQLite connection and lifecycle helpers.

The static prototype does not query SQLite yet. Keeping database ownership here
makes the eventual persistence layer a drop-in addition rather than a rewrite.
"""

import sqlite3
from pathlib import Path

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    address TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS grocery_items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    store_id INTEGER REFERENCES stores(id),
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection() -> sqlite3.Connection:
    if "db" not in g:
        path = Path(current_app.config["DATABASE"])
        path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_connection(_error=None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def initialize_schema() -> None:
    get_connection().executescript(SCHEMA)
    get_connection().commit()


def validate_import(path: str | Path) -> bool:
    """Lightweight guard for a future database import workflow."""
    try:
        with sqlite3.connect(path) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            return bool(result and result[0] == "ok")
    except sqlite3.DatabaseError:
        return False
