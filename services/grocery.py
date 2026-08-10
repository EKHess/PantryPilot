"""Grocery and store data used by the PantryPilot views."""

import re
import sqlite3

import database

ITEMS = [
    {"name": "Bananas", "store": "Fresh Market", "quantity": 1, "added": "Aug 1, 2026"},
    {"name": "Brown rice", "store": "Superstore", "quantity": 1, "added": "Jul 28, 2026"},
    {"name": "Dish soap", "store": "Walmart", "quantity": 0, "added": "Jul 19, 2026"},
    {"name": "Eggs", "store": "Costco", "quantity": 3, "added": "Jul 15, 2026"},
    {"name": "Milk", "store": "Costco", "quantity": 0, "added": "Jul 12, 2026"},
]

STORE_NEEDS = [
    {"name": "Costco", "count": 8, "percent": 37},
    {"name": "Fresh Market", "count": 6, "percent": 28},
    {"name": "Superstore", "count": 5, "percent": 23},
    {"name": "Walmart", "count": 3, "percent": 12},
]

DEFAULT_STORES = [
    ("Costco", "#2563eb"),
    ("Fresh Market", "#16a34a"),
    ("Superstore", "#ea580c"),
    ("Walmart", "#7c3aed"),
]

STORE_NAME_MAX_LENGTH = 80
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class StoreValidationError(ValueError):
    """Raised when a store cannot be saved."""


def seed_stores() -> None:
    """Populate a new installation with the stores used by the prototype."""
    connection = database.get_connection()
    connection.executemany(
        "INSERT OR IGNORE INTO stores (name, color) VALUES (?, ?)", DEFAULT_STORES
    )
    connection.commit()


def stores() -> list[dict]:
    rows = database.get_connection().execute(
        "SELECT id, name, color FROM stores ORDER BY name COLLATE NOCASE"
    ).fetchall()
    return [dict(row) for row in rows]


def create_store(name: str, color: str) -> dict:
    clean_name = " ".join((name or "").split())
    if not clean_name:
        raise StoreValidationError("Enter a store name.")
    if len(clean_name) > STORE_NAME_MAX_LENGTH:
        raise StoreValidationError(
            f"Store names must be {STORE_NAME_MAX_LENGTH} characters or fewer."
        )
    if not COLOR_PATTERN.fullmatch(color or ""):
        raise StoreValidationError("Choose a valid store color.")

    connection = database.get_connection()
    duplicate = connection.execute(
        "SELECT 1 FROM stores WHERE name = ? COLLATE NOCASE", (clean_name,)
    ).fetchone()
    if duplicate:
        raise StoreValidationError("A store with that name already exists.")

    try:
        cursor = connection.execute(
            "INSERT INTO stores (name, color) VALUES (?, ?)",
            (clean_name, color.lower()),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        raise StoreValidationError("A store with that name already exists.") from error

    return {"id": cursor.lastrowid, "name": clean_name, "color": color.lower()}


def status_for(quantity: int) -> tuple[str, str]:
    if quantity == 0:
        return "Out", "out"
    if quantity <= 1:
        return "Low", "low"
    return "In stock", "stock"


def inventory_items() -> list[dict]:
    return [{**item, "status": status_for(item["quantity"])} for item in ITEMS]


def dashboard_data() -> dict:
    return {
        "stats": [
            ("Inventory items", 86),
            ("Low stock", 14),
            ("Out of stock", 6),
            ("Stores", len(stores())),
        ],
        "items": inventory_items()[:4],
        "stores": STORE_NEEDS,
    }


def grocery_lists() -> list[dict]:
    return [
        {"name": "Costco", "count": 8, "items": [("Milk", 0), ("Eggs", 1), ("Greek yogurt", 1)]},
        {"name": "Fresh Market", "count": 6, "items": [("Bananas", 1), ("Spinach", 0), ("Tomatoes", 1)]},
    ]
