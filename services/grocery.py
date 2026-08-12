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
CATEGORY_NAME_MAX_LENGTH = 80
USERNAME_MAX_LENGTH = 80
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class StoreValidationError(ValueError):
    """Raised when a store cannot be saved."""


class ItemValidationError(ValueError):
    """Raised when an inventory item cannot be saved."""


class CategoryValidationError(ValueError):
    """Raised when a category cannot be saved."""


class SettingsValidationError(ValueError):
    """Raised when an application setting cannot be saved."""


def username() -> str:
    row = database.get_connection().execute(
        "SELECT value FROM app_metadata WHERE key = 'username'"
    ).fetchone()
    return row["value"] if row else ""


def update_username(value) -> str:
    clean_username = " ".join((value or "").split())
    if not clean_username:
        raise SettingsValidationError("Enter a username.")
    if len(clean_username) > USERNAME_MAX_LENGTH:
        raise SettingsValidationError(
            f"Username must be {USERNAME_MAX_LENGTH} characters or fewer."
        )
    connection = database.get_connection()
    connection.execute(
        """INSERT INTO app_metadata (key, value) VALUES ('username', ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        (clean_username,),
    )
    connection.commit()
    return clean_username


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


def pdf_font_size() -> int:
    row = database.get_connection().execute(
        "SELECT value FROM app_metadata WHERE key = 'pdf_font_size'"
    ).fetchone()
    return int(row["value"]) if row else int(current_app.config["PDF_FONT_SIZE"])


def update_pdf_font_size(value) -> int:
    try:
        font_size = int(value)
    except (TypeError, ValueError) as error:
        raise SettingsValidationError(
            "PDF font size must be a whole number."
        ) from error
    if not 8 <= font_size <= 32:
        raise SettingsValidationError("PDF font size must be between 8 and 32.")
    connection = database.get_connection()
    connection.execute(
        """INSERT INTO app_metadata (key, value) VALUES ('pdf_font_size', ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        (str(font_size),),
    )
    connection.commit()
    return font_size


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


def seed_categories() -> None:
    """Ensure the miscellaneous fallback exists and assign it to uncategorized items."""
    connection = database.get_connection()
    connection.execute(
        "INSERT OR IGNORE INTO categories (name, color) VALUES ('misc', '#64748b')"
    )
    misc_id = connection.execute(
        "SELECT id FROM categories WHERE name = 'misc' COLLATE NOCASE"
    ).fetchone()["id"]
    connection.execute(
        "UPDATE grocery_items SET category_id = ? WHERE category_id IS NULL", (misc_id,)
    )
    connection.commit()


def categories() -> list[dict]:
    rows = database.get_connection().execute(
        "SELECT id, name, color FROM categories ORDER BY name COLLATE NOCASE"
    ).fetchall()
    return [dict(row) for row in rows]


def get_category(category_id: int) -> dict | None:
    row = database.get_connection().execute(
        "SELECT id, name, color FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    return dict(row) if row else None


def _validated_category_values(name: str, color: str) -> tuple[str, str]:
    clean_name = " ".join((name or "").split())
    if not clean_name:
        raise CategoryValidationError("Enter a category name.")
    if len(clean_name) > CATEGORY_NAME_MAX_LENGTH:
        raise CategoryValidationError(
            f"Category names must be {CATEGORY_NAME_MAX_LENGTH} characters or fewer."
        )
    if not COLOR_PATTERN.fullmatch(color or ""):
        raise CategoryValidationError("Choose a valid category color.")
    return clean_name, color.lower()


def create_category(name: str, color: str) -> dict:
    clean_name, clean_color = _validated_category_values(name, color)
    connection = database.get_connection()
    try:
        cursor = connection.execute(
            "INSERT INTO categories (name, color) VALUES (?, ?)",
            (clean_name, clean_color),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        raise CategoryValidationError(
            "A category with that name already exists."
        ) from error
    return {"id": cursor.lastrowid, "name": clean_name, "color": clean_color}


def update_category(category_id: int, name: str, color: str) -> dict | None:
    existing = get_category(category_id)
    if not existing:
        return None
    clean_name, clean_color = _validated_category_values(name, color)
    if existing["name"].lower() == "misc" and clean_name.lower() != "misc":
        raise CategoryValidationError("The misc category cannot be renamed.")
    connection = database.get_connection()
    try:
        connection.execute(
            "UPDATE categories SET name = ?, color = ? WHERE id = ?",
            (clean_name, clean_color, category_id),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        raise CategoryValidationError(
            "A category with that name already exists."
        ) from error
    return {"id": category_id, "name": clean_name, "color": clean_color}


def delete_category(category_id: int) -> dict | None:
    connection = database.get_connection()
    category = get_category(category_id)
    if not category:
        return None
    if category["name"].lower() == "misc":
        raise CategoryValidationError("The misc category cannot be deleted.")
    misc_id = connection.execute(
        "SELECT id FROM categories WHERE name = 'misc' COLLATE NOCASE"
    ).fetchone()["id"]
    connection.execute(
        "UPDATE grocery_items SET category_id = ? WHERE category_id = ?",
        (misc_id, category_id),
    )
    connection.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    connection.commit()
    return category


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
        f"""SELECT i.id, i.name, i.store_id, i.category_id, i.quantity, i.created_at,
                   s.name AS store, s.color AS store_color,
                   c.name AS category, c.color AS category_color
            FROM grocery_items AS i
            LEFT JOIN stores AS s ON s.id = i.store_id
            LEFT JOIN categories AS c ON c.id = i.category_id
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
        """SELECT i.id, i.name, i.store_id, i.category_id, i.quantity, i.created_at,
                  s.name AS store, s.color AS store_color,
                  c.name AS category, c.color AS category_color
           FROM grocery_items AS i
           LEFT JOIN stores AS s ON s.id = i.store_id
           LEFT JOIN categories AS c ON c.id = i.category_id
           WHERE i.id = ?""",
        (item_id,),
    ).fetchone()
    return _item_from_row(row, item_minimum()) if row else None


def _validated_item_values(name: str, store_id, quantity, category_id=None) -> tuple[str, int, int, int]:
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
    if category_id in (None, ""):
        clean_category_id = next(
            category["id"] for category in categories() if category["name"].lower() == "misc"
        )
    else:
        try:
            clean_category_id = int(category_id)
        except (TypeError, ValueError) as error:
            raise ItemValidationError("Choose a valid category.") from error
        if not get_category(clean_category_id):
            raise ItemValidationError("Choose a valid category.")
    return clean_name, clean_store_id, clean_quantity, clean_category_id


def create_item(name: str, store_id, quantity, category_id=None) -> dict:
    clean_name, clean_store_id, clean_quantity, clean_category_id = _validated_item_values(
        name, store_id, quantity, category_id
    )
    connection = database.get_connection()
    duplicate = connection.execute(
        """SELECT 1 FROM grocery_items
           WHERE name = ? COLLATE NOCASE AND store_id = ?""",
        (clean_name, clean_store_id),
    ).fetchone()
    if duplicate:
        raise ItemValidationError(
            "An item with this name and store already is in the pantry inventory."
        )
    cursor = connection.execute(
        "INSERT INTO grocery_items (name, store_id, quantity, category_id) VALUES (?, ?, ?, ?)",
        (clean_name, clean_store_id, clean_quantity, clean_category_id),
    )
    connection.commit()
    return get_item(cursor.lastrowid)


def update_item(item_id: int, name: str, store_id, quantity, category_id=None) -> dict | None:
    if not get_item(item_id):
        return None
    clean_name, clean_store_id, clean_quantity, clean_category_id = _validated_item_values(
        name, store_id, quantity, category_id
    )
    connection = database.get_connection()
    connection.execute(
        "UPDATE grocery_items SET name = ?, store_id = ?, quantity = ?, category_id = ? WHERE id = ?",
        (clean_name, clean_store_id, clean_quantity, clean_category_id, item_id),
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


def grocery_lists(
    include_low: bool = False,
    sort_first: str = "store",
    store_id: int | None = None,
) -> list[dict]:
    """Return restock items grouped by store/category in the chosen order."""
    sort_first = "category" if sort_first == "category" else "store"
    restock_items = [
        item
        for item in inventory_items(store_id=store_id)
        if item["status"][1] == "out"
        or (include_low and item["status"][1] == "low")
    ]
    primary_key, secondary_key = (
        ("store", "category") if sort_first == "store" else ("category", "store")
    )
    primary_groups: dict[str, dict] = {}
    for item in restock_items:
        primary_name = item[primary_key]
        secondary_name = item[secondary_key]
        primary = primary_groups.setdefault(
            primary_name,
            {
                "id": item[f"{primary_key}_id"],
                "name": primary_name,
                "color": item.get(f"{primary_key}_color") or "#2d805f",
                "count": 0,
                "groups": {},
            },
        )
        secondary = primary["groups"].setdefault(
            secondary_name,
            {
                "name": secondary_name,
                "color": item.get(f"{secondary_key}_color") or "#64748b",
                "items": [],
            },
        )
        listed_item = {"name": item["name"], "quantity": item["quantity"]}
        secondary["items"].append(listed_item)
        primary["count"] += 1

    lists = []
    for primary in sorted(primary_groups.values(), key=lambda group: group["name"].lower()):
        primary["groups"] = sorted(
            primary["groups"].values(), key=lambda group: group["name"].lower()
        )
        for group in primary["groups"]:
            group["items"].sort(key=lambda item: item["name"].lower())
        primary["items"] = [
            item for group in primary["groups"] for item in group["items"]
        ]
        primary["sort_first"] = sort_first
        lists.append(primary)
    return lists
