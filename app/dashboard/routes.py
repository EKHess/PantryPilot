from flask import Blueprint,render_template
from app.db import get_db
from app.grocery_lists.service import needed_items
from app.settings.repository import get_int
bp=Blueprint("dashboard",__name__)
@bp.get("/")
def index():
    db=get_db(); threshold=get_int("restock_threshold",1); groups=needed_items()
    metrics={"items":db.execute("SELECT COUNT(*) FROM inventory_items WHERE is_active=1").fetchone()[0],"low":db.execute("SELECT COUNT(*) FROM inventory_items WHERE is_active=1 AND quantity>0 AND quantity<=COALESCE(restock_threshold,?)",(threshold,)).fetchone()[0],"out":db.execute("SELECT COUNT(*) FROM inventory_items WHERE is_active=1 AND quantity=0").fetchone()[0],"stores":db.execute("SELECT COUNT(*) FROM stores WHERE is_active=1").fetchone()[0]}
    return render_template("dashboard/index.html",metrics=metrics,groups=groups,needed=[i for items in groups.values() for i in items][:6])

