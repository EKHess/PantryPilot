"""PantryPilot Flask application entrypoint."""

import argparse
from io import BytesIO
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

import database
from config import Config
from services import grocery
from services.pdf import grocery_list_pdf


def create_app(test_config=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.from_mapping(test_config)

    app.teardown_appcontext(database.close_connection)

    with app.app_context():
        database.initialize_schema()
        grocery.seed_stores()
        grocery.seed_items()
        grocery.seed_categories()

    @app.context_processor
    def form_choices():
        return {"store_choices": grocery.stores(), "category_choices": grocery.categories()}

    @app.get("/")
    def dashboard():
        search = request.args.get("search", "").strip()
        store_id = request.args.get("store", type=int)
        return render_template(
            "dashboard.html",
            active="dashboard",
            search=search,
            selected_store=store_id,
            **grocery.dashboard_data(search, store_id),
        )

    @app.get("/inventory")
    def inventory():
        search = request.args.get("search", "").strip()
        store_id = request.args.get("store", type=int)
        requested_letter = request.args.get("letter", "All").upper()
        selected_letter = (
            requested_letter
            if len(requested_letter) == 1 and requested_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            else "All"
        )
        return render_template(
            "inventory.html",
            active="inventory",
            items=grocery.inventory_items(search, store_id, selected_letter),
            item_names=grocery.item_names(),
            search=search,
            selected_store=store_id,
            selected_letter=selected_letter,
        )

    def item_redirect():
        endpoint = request.form.get("return_to", "dashboard")
        return redirect(url_for(endpoint if endpoint in {"dashboard", "inventory"} else "dashboard"))

    @app.post("/items")
    def create_item():
        try:
            item = grocery.create_item(
                request.form.get("name", ""),
                request.form.get("store_id"),
                request.form.get("quantity"),
                request.form.get("category_id"),
            )
        except grocery.ItemValidationError as error:
            if request.accept_mimetypes.best == "application/json":
                return jsonify({"ok": False, "message": str(error)}), 400
            flash(str(error), "error")
        else:
            if request.accept_mimetypes.best == "application/json":
                return jsonify(
                    {
                        "ok": True,
                        "message": f"{item['name']} was added to the pantry.",
                    }
                ), 201
            flash(f"{item['name']} was added.", "success")
        return item_redirect()

    @app.post("/items/<int:item_id>/edit")
    def edit_item(item_id):
        try:
            item = grocery.update_item(
                item_id,
                request.form.get("name", ""),
                request.form.get("store_id"),
                request.form.get("quantity"),
                request.form.get("category_id"),
            )
        except grocery.ItemValidationError as error:
            flash(str(error), "error")
        else:
            if item is None:
                abort(404)
            flash(f"{item['name']} was updated.", "success")
        return item_redirect()

    @app.post("/items/<int:item_id>/quantity")
    def change_item_quantity(item_id):
        change = request.form.get("change", type=int)
        if change not in {-1, 1}:
            abort(400)
        item = grocery.change_item_quantity(item_id, change)
        if item is None:
            abort(404)
        return item_redirect()

    @app.post("/items/<int:item_id>/delete")
    def delete_item(item_id):
        item = grocery.delete_item(item_id)
        if item is None:
            abort(404)
        flash(f"{item['name']} was deleted.", "success")
        return item_redirect()

    @app.get("/grocery-lists")
    def grocery_lists():
        include_low = request.args.get("include_low") == "1"
        sort_first = (
            "category" if request.args.get("sort_first") == "category" else "store"
        )
        lists = grocery.grocery_lists(include_low=include_low, sort_first=sort_first)
        return render_template(
            "grocery_lists.html",
            active="lists",
            lists=lists,
            list_item_count=sum(grocery_list["count"] for grocery_list in lists),
            include_low=include_low,
            sort_first=sort_first,
        )

    def pdf_download(lists, filename, title):
        return send_file(
            BytesIO(grocery_list_pdf(lists, title, grocery.pdf_font_size())),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )

    @app.get("/grocery-lists/download")
    def download_all_grocery_lists():
        lists = grocery.grocery_lists(
            request.args.get("include_low") == "1",
            request.args.get("sort_first", "store"),
        )
        return pdf_download(
            lists, "pantrypilot-grocery-lists.pdf", "Compiled Grocery List"
        )

    @app.get("/grocery-lists/stores/<int:store_id>/download")
    def download_store_grocery_list(store_id):
        store = grocery.get_store(store_id)
        if store is None:
            abort(404)
        sort_first = request.args.get("sort_first", "store")
        lists = grocery.grocery_lists(
            request.args.get("include_low") == "1", sort_first, store_id
        )
        if not lists:
            lists = [
                {
                    "id": store_id,
                    "name": store["name"],
                    "color": store["color"],
                    "items": [],
                    "groups": [],
                    "count": 0,
                }
            ]
        filename = re.sub(r"[^a-z0-9]+", "-", store["name"].lower()).strip("-")
        return pdf_download(
            lists,
            f"{filename}-grocery-list.pdf",
            f"{store['name']} Grocery List",
        )

    @app.route("/stores", methods=["GET", "POST"])
    def stores():
        if request.method == "POST":
            try:
                store = grocery.create_store(
                    request.form.get("name", ""), request.form.get("color", "")
                )
            except grocery.StoreValidationError as error:
                flash(str(error), "error")
            else:
                flash(f"{store['name']} was added.", "success")
            return redirect(url_for("stores"))
        return render_template("stores.html", active="stores", stores=grocery.stores())

    @app.post("/stores/<int:store_id>/edit")
    def edit_store(store_id):
        try:
            store = grocery.update_store(
                store_id, request.form.get("name", ""), request.form.get("color", "")
            )
        except grocery.StoreValidationError as error:
            flash(str(error), "error")
        else:
            if store is None:
                abort(404)
            flash(f"{store['name']} was updated.", "success")
        return redirect(url_for("stores"))

    @app.post("/stores/<int:store_id>/delete")
    def delete_store(store_id):
        store = grocery.delete_store(store_id)
        if store is None:
            abort(404)
        flash(f"{store['name']} was deleted.", "success")
        return redirect(url_for("stores"))

    @app.route("/categories", methods=["GET", "POST"])
    def categories():
        if request.method == "POST":
            try:
                category = grocery.create_category(
                    request.form.get("name", ""), request.form.get("color", "")
                )
            except grocery.CategoryValidationError as error:
                flash(str(error), "error")
            else:
                flash(f"{category['name']} was added.", "success")
            return redirect(url_for("categories"))
        return render_template("categories.html", active="categories", categories=grocery.categories())

    @app.post("/categories/<int:category_id>/edit")
    def edit_category(category_id):
        try:
            category = grocery.update_category(
                category_id, request.form.get("name", ""), request.form.get("color", "")
            )
        except grocery.CategoryValidationError as error:
            flash(str(error), "error")
        else:
            if category is None:
                abort(404)
            flash(f"{category['name']} was updated.", "success")
        return redirect(url_for("categories"))

    @app.post("/categories/<int:category_id>/delete")
    def delete_category(category_id):
        try:
            category = grocery.delete_category(category_id)
        except grocery.CategoryValidationError as error:
            flash(str(error), "error")
        else:
            if category is None:
                abort(404)
            flash(f"{category['name']} was deleted.", "success")
        return redirect(url_for("categories"))

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        if request.method == "POST":
            try:
                if "pdf_font_size" in request.form:
                    font_size = grocery.update_pdf_font_size(
                        request.form.get("pdf_font_size")
                    )
                    message = f"PDF font size was updated to {font_size}."
                else:
                    minimum = grocery.update_item_minimum(
                        request.form.get("item_minimum")
                    )
                    message = f"Item Minimum was updated to {minimum}."
            except grocery.SettingsValidationError as error:
                flash(str(error), "error")
            else:
                flash(message, "success")
            return redirect(url_for("settings"))
        return render_template(
            "settings.html",
            active="settings",
            item_minimum=grocery.item_minimum(),
            pdf_font_size=grocery.pdf_font_size(),
        )

    @app.get("/export")
    def export_backup():
        return render_template("export.html", active="export")

    @app.get("/export/download")
    def download_backup():
        backup = BytesIO()
        with tempfile.TemporaryDirectory() as temporary_directory:
            snapshot_path = Path(temporary_directory) / "pantrypilot-backup.db"
            with sqlite3.connect(snapshot_path) as snapshot:
                database.get_connection().backup(snapshot)
            backup.write(snapshot_path.read_bytes())
        backup.seek(0)
        return send_file(
            backup,
            mimetype="application/vnd.sqlite3",
            as_attachment=True,
            download_name="pantrypilot-backup.db",
        )

    @app.route("/import", methods=["GET", "POST"])
    def import_backup():
        if request.method == "POST":
            uploaded = request.files.get("database")
            if uploaded is None or not uploaded.filename:
                flash("Choose a PantryPilot .db file to import.", "error")
                return redirect(url_for("import_backup"))
            if Path(uploaded.filename).suffix.lower() != ".db":
                flash("The selected file must have a .db extension.", "error")
                return redirect(url_for("import_backup"))

            database_path = Path(app.config["DATABASE"])
            database_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, upload_path_string = tempfile.mkstemp(
                prefix="pantrypilot-import-", suffix=".db", dir=database_path.parent
            )
            os.close(descriptor)
            upload_path = Path(upload_path_string)
            try:
                uploaded.save(upload_path)
                if not database.validate_import(upload_path):
                    flash(
                        "That file is not a compatible PantryPilot database. Your pantry was not changed.",
                        "error",
                    )
                    return redirect(url_for("import_backup"))
                database.close_connection()
                os.replace(upload_path, database_path)
                database.initialize_schema()
            finally:
                upload_path.unlink(missing_ok=True)
            flash("Your PantryPilot backup was imported successfully.", "success")
            return redirect(url_for("inventory"))
        return render_template("import.html", active="import")

    return app


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A local Flask app to manage grocery inventory")
    parser.add_argument("--port", type=int, default=8888, help="Port to run on local host (default: 8888)")
    args = parser.parse_args()

    app.run(debug=True, host='0.0.0.0', port=args.port)
