from sqlite3 import IntegrityError
from flask import Blueprint, jsonify, render_template, request
from . import repository
from app.stores.repository import list_stores

bp = Blueprint("inventory", __name__)


def error(message, fields=None, status=400, code="validation_error"):
    return jsonify(error={"code": code, "message": message, "fields": fields or {}}), status


def serialize(row):
    value = dict(row); threshold = value.get("effective_threshold", 1)
    value["status"] = "out" if value["quantity"] == 0 else ("low" if value["quantity"] <= threshold else "in_stock")
    return value


@bp.get("/inventory")
def page():
    items = [serialize(row) for row in repository.list_items(request.args)]
    return render_template("inventory/index.html", items=items, stores=list_stores(), filters=request.args)


@bp.get("/api/inventory")
def index(): return jsonify(items=[serialize(row) for row in repository.list_items(request.args)])


@bp.post("/api/inventory")
def create():
    data = request.get_json(silent=True)
    if not isinstance(data, dict): return error("A JSON object is required.")
    name = str(data.get("name", "")).strip()
    try: quantity, store_id = int(data.get("quantity", 0)), int(data.get("store_id", 0))
    except (TypeError, ValueError): return error("Quantity and store must be whole numbers.")
    if not name or len(name) > 100: return error("Enter an item name of 1–100 characters.", {"name": "Name is required."})
    if quantity < 0 or not store_id: return error("Quantity must be zero or greater and a store is required.")
    data.update(name=name, quantity=quantity, store_id=store_id)
    try: item = repository.create_item(data)
    except IntegrityError: return error("That item already exists at this store.", status=409, code="duplicate_item")
    return jsonify(item=serialize(item)), 201


@bp.patch("/api/inventory/<int:item_id>/quantity")
def quantity(item_id):
    data = request.get_json(silent=True) or {}; item = repository.get_item(item_id)
    if not item: return error("Item not found.", status=404, code="not_found")
    try:
        if "quantity" in data: new = int(data["quantity"])
        else:
            amount = int(data.get("amount", 1)); new = item["quantity"] + (amount if data.get("operation") == "increment" else -amount)
        updated = repository.adjust_quantity(item_id, new, data.get("reason"))
    except (ValueError, TypeError): return error("Quantity must be a whole number of zero or greater.", {"quantity": "Enter zero or greater."})
    result = dict(updated); result["effective_threshold"] = item["restock_threshold"] if item["restock_threshold"] is not None else 1
    return jsonify(item=serialize(result))


@bp.get("/api/inventory/suggestions")
def suggestions():
    query = request.args.get("q", "").strip()
    if len(query) < 2: return jsonify(suggestions=[])
    return jsonify(suggestions=[{"id": r["id"], "name": r["name"], "store": r["store_name"]} for r in repository.list_items({"q": query})[:10]])

