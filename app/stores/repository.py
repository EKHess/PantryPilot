from app.db import get_db


def list_stores(active_only=True):
    where = "WHERE s.is_active=1" if active_only else ""
    return get_db().execute(f"SELECT s.*, COUNT(i.id) item_count FROM stores s LEFT JOIN inventory_items i ON i.store_id=s.id AND i.is_active=1 {where} GROUP BY s.id ORDER BY s.display_order, s.name").fetchall()


def create_store(name, address="", display_order=0):
    db=get_db(); cursor=db.execute("INSERT INTO stores(name,address,display_order) VALUES(?,?,?)", (name,address,display_order)); db.commit()
    return db.execute("SELECT * FROM stores WHERE id=?",(cursor.lastrowid,)).fetchone()

