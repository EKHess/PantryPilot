"""SQLite connection and lifecycle helpers."""

import sqlite3
from pathlib import Path
from typing import Iterable

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    color TEXT NOT NULL DEFAULT '#2d805f',
    address TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS grocery_items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    store_id INTEGER REFERENCES stores(id),
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    color TEXT NOT NULL DEFAULT '#64748b'
);
CREATE TABLE IF NOT EXISTS app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
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
    columns = {row["name"] for row in get_connection().execute("PRAGMA table_info(stores)")}
    if "color" not in columns:
        get_connection().execute(
            "ALTER TABLE stores ADD COLUMN color TEXT NOT NULL DEFAULT '#2d805f'"
        )
    item_columns = {
        row["name"] for row in get_connection().execute("PRAGMA table_info(grocery_items)")
    }
    if "category_id" not in item_columns:
        get_connection().execute(
            "ALTER TABLE grocery_items ADD COLUMN category_id INTEGER REFERENCES categories(id)"
        )
    get_connection().commit()


REQUIRED_IMPORT_COLUMNS = {
    "stores": {"id", "name"},
    "grocery_items": {"id", "name", "store_id", "quantity"},
}


def _table_columns(connection: sqlite3.Connection, table: str) -> Iterable[str]:
    return (row[1] for row in connection.execute(f"PRAGMA table_info({table})"))


def validate_import(path: str | Path) -> bool:
    """Return whether a file is an intact, compatible PantryPilot database."""
    try:
        with sqlite3.connect(path) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                return False
            return all(
                required.issubset(set(_table_columns(connection, table)))
                for table, required in REQUIRED_IMPORT_COLUMNS.items()
            )
    except sqlite3.DatabaseError:
        return False
