"""Grocery and store data used by the PantryPilot views."""

import re
import sqlite3

import database

ITEMS = [
    {"name": "Bananas", "store_id": 2, "quantity": 1, "added": "Aug 1, 2026"},
    {"name": "Brown rice", "store_id": 3, "quantity": 1, "added": "Jul 28, 2026"},
    {"name": "Dish soap", "store_id": 4, "quantity": 0, "added": "Jul 19, 2026"},
    {"name": "Eggs", "store_id": 1, "quantity": 3, "added": "Jul 15, 2026"},
    {"name": "Milk", "store_id": 1, "quantity": 0, "added": "Jul 12, 2026"},
]

STORE_NEEDS = [
    {"store_id": 1, "count": 8, "percent": 37},
    {"store_id": 2, "count": 6, "percent": 28},
    {"store_id": 3, "count": 5, "percent": 23},
    {"store_id": 4, "count": 3, "percent": 12},
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
    """Populate stores once, without restoring stores a user later deletes."""
    connection = database.get_connection()
    seeded = connection.execute(
        "SELECT 1 FROM app_metadata WHERE key = 'default_stores_seeded'"
    ).fetchone()
    if seeded:
        return
    connection.executemany(
        "INSERT OR IGNORE INTO stores (name, color) VALUES (?, ?)", DEFAULT_STORES
    )
    connection.execute(
        "INSERT INTO app_metadata (key, value) VALUES ('default_stores_seeded', '1')"
    )
    connection.commit()


def stores() -> list[dict]:
    rows = database.get_connection().execute(
        "SELECT id, name, color FROM stores ORDER BY name COLLATE NOCASE"
    ).fetchall()
    return [dict(row) for row in rows]


def get_store(store_id: int) -> dict | None:
    row = database.get_connection().execute(
        "SELECT id, name, color FROM stores WHERE id = ?", (store_id,)
    ).fetchone()
    return dict(row) if row else None


def _validated_store_values(name: str, color: str) -> tuple[str, str]:
    """Normalize and validate values shared by create and update operations."""
    clean_name = " ".join((name or "").split())
    if not clean_name:
        raise StoreValidationError("Enter a store name.")
    if len(clean_name) > STORE_NAME_MAX_LENGTH:
        raise StoreValidationError(
            f"Store names must be {STORE_NAME_MAX_LENGTH} characters or fewer."
        )
    if not COLOR_PATTERN.fullmatch(color or ""):
        raise StoreValidationError("Choose a valid store color.")
    return clean_name, color.lower()


def create_store(name: str, color: str) -> dict:
    clean_name, clean_color = _validated_store_values(name, color)

    connection = database.get_connection()
    duplicate = connection.execute(
        "SELECT 1 FROM stores WHERE name = ? COLLATE NOCASE", (clean_name,)
    ).fetchone()
    if duplicate:
        raise StoreValidationError("A store with that name already exists.")

    try:
        cursor = connection.execute(
            "INSERT INTO stores (name, color) VALUES (?, ?)",
            (clean_name, clean_color),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        raise StoreValidationError("A store with that name already exists.") from error

    return {"id": cursor.lastrowid, "name": clean_name, "color": clean_color}


def update_store(store_id: int, name: str, color: str) -> dict | None:
    connection = database.get_connection()
    if not get_store(store_id):
        return None
    clean_name, clean_color = _validated_store_values(name, color)
    duplicate = connection.execute(
        "SELECT 1 FROM stores WHERE name = ? COLLATE NOCASE AND id != ?",
        (clean_name, store_id),
    ).fetchone()
    if duplicate:
        raise StoreValidationError("A store with that name already exists.")
    try:
        connection.execute(
            "UPDATE stores SET name = ?, color = ? WHERE id = ?",
            (clean_name, clean_color, store_id),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        raise StoreValidationError("A store with that name already exists.") from error
    return {"id": store_id, "name": clean_name, "color": clean_color}


def delete_store(store_id: int) -> dict | None:
    connection = database.get_connection()
    store = get_store(store_id)
    if not store:
        return None
    connection.execute("UPDATE grocery_items SET store_id = NULL WHERE store_id = ?", (store_id,))
    connection.execute("DELETE FROM stores WHERE id = ?", (store_id,))
    connection.commit()
    return store


def status_for(quantity: int) -> tuple[str, str]:
    if quantity == 0:
        return "Out", "out"
    if quantity <= 1:
        return "Low", "low"
    return "In stock", "stock"


def inventory_items() -> list[dict]:
    store_names = {store["id"]: store["name"] for store in stores()}
    return [
        {
            **item,
            "store": store_names.get(item["store_id"], "Unassigned"),
            "status": status_for(item["quantity"]),
        }
        for item in ITEMS
    ]


def dashboard_data() -> dict:
    current_stores = stores()
    store_names = {store["id"]: store["name"] for store in current_stores}
    return {
        "stats": [
            ("Inventory items", 86),
            ("Low stock", 14),
            ("Out of stock", 6),
            ("Stores", len(current_stores)),
        ],
        "items": inventory_items()[:4],
        "stores": [
            {**store, "name": store_names[store["store_id"]]}
            for store in STORE_NEEDS
            if store["store_id"] in store_names
        ],
    }


def grocery_lists() -> list[dict]:
    store_names = {store["id"]: store["name"] for store in stores()}
    lists = [
        {"store_id": 1, "count": 8, "items": [("Milk", 0), ("Eggs", 1), ("Greek yogurt", 1)]},
        {"store_id": 2, "count": 6, "items": [("Bananas", 1), ("Spinach", 0), ("Tomatoes", 1)]},
    ]
    return [
        {**grocery_list, "name": store_names[grocery_list["store_id"]]}
        for grocery_list in lists
        if grocery_list["store_id"] in store_names
    ]
