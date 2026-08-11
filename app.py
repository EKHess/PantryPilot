"""PantryPilot Flask application entrypoint."""

import argparse
from io import BytesIO
import re

from flask import (
    Flask,
    abort,
    flash,
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

    @app.context_processor
    def store_choices():
        return {"store_choices": grocery.stores()}

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
            )
        except grocery.ItemValidationError as error:
            flash(str(error), "error")
        else:
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
        lists = grocery.grocery_lists(include_low=include_low)
        return render_template(
            "grocery_lists.html",
            active="lists",
            lists=lists,
            list_item_count=sum(grocery_list["count"] for grocery_list in lists),
            include_low=include_low,
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
        lists = grocery.grocery_lists(request.args.get("include_low") == "1")
        return pdf_download(lists, "pantrypilot-grocery-lists.pdf", "Grocery Lists")

    @app.get("/grocery-lists/stores/<int:store_id>/download")
    def download_store_grocery_list(store_id):
        store = grocery.get_store(store_id)
        if store is None:
            abort(404)
        lists = [
            grocery_list
            for grocery_list in grocery.grocery_lists(
                request.args.get("include_low") == "1"
            )
            if grocery_list["id"] == store_id
        ]
        if not lists:
            lists = [
                {
                    "id": store_id,
                    "name": store["name"],
                    "color": store["color"],
                    "items": [],
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

    return app


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A local Flask app to manage grocery inventory")
    parser.add_argument("--port", type=int, default=8888, help="Port to run on local host (default: 8888)")
    args = parser.parse_args()

    app.run(debug=True, host='0.0.0.0', port=args.port)
