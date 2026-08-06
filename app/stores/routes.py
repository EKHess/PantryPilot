from sqlite3 import IntegrityError
from flask import Blueprint, jsonify, render_template, request
from app.db import get_db
from .repository import create_store, list_stores

bp=Blueprint("stores",__name__)

@bp.get("/stores")
def page(): return render_template("stores/index.html", stores=list_stores(False))

@bp.get("/api/stores")
def index(): return jsonify(stores=[dict(s) for s in list_stores(False)])

@bp.post("/api/stores")
def create():
    data=request.get_json(silent=True) or {}; name=str(data.get("name","")).strip()
    if not name or len(name)>80: return jsonify(error={"code":"validation_error","message":"Store name is required."}),400
    try: store=create_store(name,str(data.get("address","")).strip(),int(data.get("display_order",0)))
    except IntegrityError: return jsonify(error={"code":"duplicate_store","message":"That store already exists."}),409
    return jsonify(store=dict(store)),201

@bp.patch("/api/stores/<int:store_id>")
def update(store_id):
    data=request.get_json(silent=True) or {}; db=get_db(); store=db.execute("SELECT * FROM stores WHERE id=?",(store_id,)).fetchone()
    if not store: return jsonify(error={"code":"not_found","message":"Store not found."}),404
    db.execute("UPDATE stores SET name=?,address=?,display_order=?,is_active=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(str(data.get("name",store["name"])).strip(),data.get("address",store["address"]),int(data.get("display_order",store["display_order"])),int(data.get("is_active",store["is_active"])),store_id)); db.commit()
    return jsonify(store=dict(db.execute("SELECT * FROM stores WHERE id=?",(store_id,)).fetchone()))

@bp.delete("/api/stores/<int:store_id>")
def delete(store_id):
    db=get_db(); count=db.execute("SELECT COUNT(*) FROM inventory_items WHERE store_id=?",(store_id,)).fetchone()[0]
    if count: return jsonify(error={"code":"store_in_use","message":"Reassign or archive this store's inventory first."}),409
    if not db.execute("DELETE FROM stores WHERE id=?",(store_id,)).rowcount: return jsonify(error={"code":"not_found","message":"Store not found."}),404
    db.commit(); return "",204

