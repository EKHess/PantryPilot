"""Grocery and store data used by the PantryPilot views."""

import re
import sqlite3
from datetime import datetime

from flask import current_app

import database

DEFAULT_STORES = [
    ("Costco", "#2563eb"),
    ("Fresh Market", "#16a34a"),
    ("Superstore", "#ea580c"),
    ("Walmart", "#7c3aed"),
]

DEFAULT_ITEMS = [
    ("Bananas", 2, 1, "2026-08-01 09:00:00"),
    ("Brown rice", 3, 1, "2026-07-28 09:00:00"),
    ("Dish soap", 4, 0, "2026-07-19 09:00:00"),
    ("Eggs", 1, 3, "2026-07-15 09:00:00"),
    ("Milk", 1, 0, "2026-07-12 09:00:00"),
]

STORE_NAME_MAX_LENGTH = 80
ITEM_NAME_MAX_LENGTH = 120
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class StoreValidationError(ValueError):
    """Raised when a store cannot be saved."""


class ItemValidationError(ValueError):
    """Raised when an inventory item cannot be saved."""


class SettingsValidationError(ValueError):
    """Raised when an application setting cannot be saved."""


def item_minimum() -> int:
    row = database.get_connection().execute(
        "SELECT value FROM app_metadata WHERE key = 'item_minimum'"
    ).fetchone()
    return int(row["value"]) if row else int(current_app.config["RESTOCK_THRESHOLD"])


def update_item_minimum(value) -> int:
    try:
        minimum = int(value)
    except (TypeError, ValueError) as error:
        raise SettingsValidationError("Item Minimum must be a whole number.") from error
    if minimum < 0:
        raise SettingsValidationError("Item Minimum cannot be negative.")
    connection = database.get_connection()
    connection.execute(
        """INSERT INTO app_metadata (key, value) VALUES ('item_minimum', ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        (str(minimum),),
    )
    connection.commit()
    return minimum


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


def seed_items() -> None:
    """Populate the prototype inventory once so it becomes user-editable."""
    connection = database.get_connection()
    seeded = connection.execute(
        "SELECT 1 FROM app_metadata WHERE key = 'default_items_seeded'"
    ).fetchone()
    if seeded:
        return
    available_store_ids = {store["id"] for store in stores()}
    default_items = [item for item in DEFAULT_ITEMS if item[1] in available_store_ids]
    connection.executemany(
        "INSERT INTO grocery_items (name, store_id, quantity, created_at) VALUES (?, ?, ?, ?)",
        default_items,
    )
    connection.execute(
        "INSERT INTO app_metadata (key, value) VALUES ('default_items_seeded', '1')"
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


def status_for(quantity: int, minimum: int) -> tuple[str, str]:
    if quantity == 0:
        return "Out", "out"
    if quantity <= minimum:
        return "Low", "low"
    return "In Stock", "stock"


def _item_from_row(row, minimum: int) -> dict:
    item = dict(row)
    item["store"] = item["store"] or "Unassigned"
    item["added"] = datetime.fromisoformat(item.pop("created_at")).strftime("%b %d, %Y")
    item["status"] = status_for(item["quantity"], minimum)
    return item


def inventory_items(
    search: str = "", store_id: int | None = None, letter: str = "All"
) -> list[dict]:
    minimum = item_minimum()
    clauses = []
    parameters: list = []
    if search:
        clauses.append("i.name LIKE ? COLLATE NOCASE")
        parameters.append(f"%{search.strip()}%")
    if store_id is not None:
        clauses.append("i.store_id = ?")
        parameters.append(store_id)
    if len(letter) == 1 and letter.isascii() and letter.isalpha():
        clauses.append("i.name LIKE ? COLLATE NOCASE")
        parameters.append(f"{letter}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = database.get_connection().execute(
        f"""SELECT i.id, i.name, i.store_id, i.quantity, i.created_at,
                   s.name AS store
            FROM grocery_items AS i
            LEFT JOIN stores AS s ON s.id = i.store_id
            {where}
            ORDER BY i.name COLLATE NOCASE""",
        parameters,
    ).fetchall()
    return [_item_from_row(row, minimum) for row in rows]


def item_names() -> list[str]:
    rows = database.get_connection().execute(
        "SELECT DISTINCT name FROM grocery_items ORDER BY name COLLATE NOCASE"
    ).fetchall()
    return [row["name"] for row in rows]


def get_item(item_id: int) -> dict | None:
    row = database.get_connection().execute(
        """SELECT i.id, i.name, i.store_id, i.quantity, i.created_at,
                  s.name AS store
           FROM grocery_items AS i
           LEFT JOIN stores AS s ON s.id = i.store_id
           WHERE i.id = ?""",
        (item_id,),
    ).fetchone()
    return _item_from_row(row, item_minimum()) if row else None


def _validated_item_values(name: str, store_id, quantity) -> tuple[str, int, int]:
    clean_name = " ".join((name or "").split())
    if not clean_name:
        raise ItemValidationError("Enter an item name.")
    if len(clean_name) > ITEM_NAME_MAX_LENGTH:
        raise ItemValidationError(
            f"Item names must be {ITEM_NAME_MAX_LENGTH} characters or fewer."
        )
    try:
        clean_store_id = int(store_id)
    except (TypeError, ValueError) as error:
        raise ItemValidationError("Choose a valid store.") from error
    if not get_store(clean_store_id):
        raise ItemValidationError("Choose a valid store.")
    try:
        clean_quantity = int(quantity)
    except (TypeError, ValueError) as error:
        raise ItemValidationError("Quantity must be a whole number.") from error
    if clean_quantity < 0:
        raise ItemValidationError("Quantity cannot be negative.")
    return clean_name, clean_store_id, clean_quantity


def create_item(name: str, store_id, quantity) -> dict:
    clean_name, clean_store_id, clean_quantity = _validated_item_values(
        name, store_id, quantity
    )
    connection = database.get_connection()
    cursor = connection.execute(
        "INSERT INTO grocery_items (name, store_id, quantity) VALUES (?, ?, ?)",
        (clean_name, clean_store_id, clean_quantity),
    )
    connection.commit()
    return get_item(cursor.lastrowid)


def update_item(item_id: int, name: str, store_id, quantity) -> dict | None:
    if not get_item(item_id):
        return None
    clean_name, clean_store_id, clean_quantity = _validated_item_values(
        name, store_id, quantity
    )
    connection = database.get_connection()
    connection.execute(
        "UPDATE grocery_items SET name = ?, store_id = ?, quantity = ? WHERE id = ?",
        (clean_name, clean_store_id, clean_quantity, item_id),
    )
    connection.commit()
    return get_item(item_id)


def change_item_quantity(item_id: int, change: int) -> dict | None:
    connection = database.get_connection()
    item = get_item(item_id)
    if not item:
        return None
    quantity = max(0, item["quantity"] + change)
    connection.execute(
        "UPDATE grocery_items SET quantity = ? WHERE id = ?", (quantity, item_id)
    )
    connection.commit()
    return get_item(item_id)


def delete_item(item_id: int) -> dict | None:
    connection = database.get_connection()
    item = get_item(item_id)
    if not item:
        return None
    connection.execute("DELETE FROM grocery_items WHERE id = ?", (item_id,))
    connection.commit()
    return item


def dashboard_data(search: str = "", store_id: int | None = None) -> dict:
    current_stores = stores()
    items = inventory_items(search, store_id)
    all_items = inventory_items()
    out_count = sum(item["quantity"] == 0 for item in all_items)
    low_count = sum(item["status"][1] == "low" for item in all_items)
    in_stock_count = len(all_items) - out_count - low_count
    counts = {store["id"]: 0 for store in current_stores}
    for item in all_items:
        if item["status"][1] in {"out", "low"} and item["store_id"] in counts:
            counts[item["store_id"]] += 1
    total_restock = sum(counts.values())
    return {
        "stats": [
            ("Inventory items", len(all_items)),
            ("In stock", in_stock_count),
            ("Low stock", low_count),
            ("Out of stock", out_count),
        ],
        "items": items,
        "item_names": item_names(),
        "stores": [
            {
                **store,
                "count": counts[store["id"]],
                "percent": (
                    round(counts[store["id"]] / total_restock * 100)
                    if total_restock
                    else 0
                ),
            }
            for store in current_stores
            if counts[store["id"]]
        ],
    }


def grocery_lists(include_low: bool = False) -> list[dict]:
    """Return automatically generated restock lists grouped by store.

    Out-of-stock items are always included. Low-stock items are opt-in so the
    same function can drive both the page and its PDF downloads.
    """
    lists = []
    for store in stores():
        items = [
            {"name": item["name"], "quantity": item["quantity"]}
            for item in inventory_items(store_id=store["id"])
            if item["status"][1] == "out"
            or (include_low and item["status"][1] == "low")
        ]
        if items:
            lists.append(
                {
                    "id": store["id"],
                    "name": store["name"],
                    "color": store["color"],
                    "count": len(items),
                    "items": items,
                }
            )
    return lists
