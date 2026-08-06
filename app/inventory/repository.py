from sqlite3 import IntegrityError
from app.db import get_db

SORT_COLUMNS = {"name": "i.name", "store": "s.name", "quantity": "i.quantity", "created": "i.created_at", "updated": "i.updated_at"}


def list_items(filters=None):
    filters = filters or {}
    clauses, values = ["i.is_active = 1"], []
    if filters.get("q"):
        clauses.append("i.name LIKE ?"); values.append(f"%{filters['q']}%")
    if filters.get("store"):
        clauses.append("i.store_id = ?"); values.append(filters["store"])
    if filters.get("letter"):
        clauses.append("i.name LIKE ?"); values.append(f"{filters['letter'][0]}%")
    if filters.get("date_from"):
        clauses.append("date(i.created_at) >= date(?)"); values.append(filters["date_from"])
    if filters.get("date_to"):
        clauses.append("date(i.created_at) <= date(?)"); values.append(filters["date_to"])
    sort = SORT_COLUMNS.get(filters.get("sort"), "i.name")
    direction = "DESC" if filters.get("direction") == "desc" else "ASC"
    sql = f"SELECT i.*, s.name store_name, COALESCE(i.restock_threshold, CAST(gs.value AS INTEGER)) effective_threshold FROM inventory_items i JOIN stores s ON s.id=i.store_id JOIN settings gs ON gs.key='restock_threshold' WHERE {' AND '.join(clauses)} ORDER BY {sort} {direction}, i.id"
    return get_db().execute(sql, values).fetchall()


def get_item(item_id):
    return get_db().execute("SELECT * FROM inventory_items WHERE id=?", (item_id,)).fetchone()


def create_item(data):
    db = get_db()
    cursor = db.execute("INSERT INTO inventory_items(name,quantity,unit,store_id,restock_threshold,target_quantity,aisle,notes) VALUES(?,?,?,?,?,?,?,?)", (data["name"], data["quantity"], data.get("unit", "item"), data["store_id"], data.get("restock_threshold"), data.get("target_quantity"), data.get("aisle"), data.get("notes")))
    db.commit(); return get_item(cursor.lastrowid)


def adjust_quantity(item_id, new_quantity, reason=None):
    db = get_db(); item = get_item(item_id)
    if not item: return None
    if new_quantity < 0: raise ValueError("Quantity cannot be negative.")
    with db:
        db.execute("UPDATE inventory_items SET quantity=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_quantity, item_id))
        db.execute("INSERT INTO inventory_adjustments(inventory_item_id,previous_quantity,new_quantity,change_amount,reason) VALUES(?,?,?,?,?)", (item_id, item["quantity"], new_quantity, new_quantity-item["quantity"], reason))
    return get_item(item_id)

