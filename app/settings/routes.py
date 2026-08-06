from flask import Blueprint,jsonify,render_template,request
from .repository import all_settings,update_settings
bp=Blueprint("settings",__name__)
ALLOWED={"restock_threshold","default_target_quantity","theme","items_per_page","pdf_show_current_quantity","pdf_show_purchase_quantity"}
@bp.get("/settings")
def page(): return render_template("settings/index.html", settings=all_settings())
@bp.get("/api/settings")
def index(): return jsonify(settings=all_settings())
@bp.patch("/api/settings")
def update():
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or any(k not in ALLOWED for k in data): return jsonify(error={"code":"validation_error","message":"One or more settings are invalid."}),400
    for key in ("restock_threshold","default_target_quantity","items_per_page"):
        if key in data:
            try:
                if int(data[key])<0: raise ValueError
            except (ValueError,TypeError): return jsonify(error={"code":"validation_error","message":f"{key} must be zero or greater."}),400
    update_settings(data); return jsonify(settings=all_settings())

