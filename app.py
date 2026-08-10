"""PantryPilot Flask application entrypoint."""

from flask import Flask, abort, flash, redirect, render_template, request, url_for
import argparse

import database
from config import Config
from services import grocery


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
        return render_template(
            "inventory.html",
            active="inventory",
            items=grocery.inventory_items(search, store_id),
            item_names=grocery.item_names(),
            search=search,
            selected_store=store_id,
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
        lists = grocery.grocery_lists()
        return render_template(
            "grocery_lists.html",
            active="lists",
            lists=lists,
            list_item_count=sum(grocery_list["count"] for grocery_list in lists),
            item_minimum=grocery.item_minimum(),
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
                minimum = grocery.update_item_minimum(
                    request.form.get("item_minimum")
                )
            except grocery.SettingsValidationError as error:
                flash(str(error), "error")
            else:
                flash(f"Item Minimum was updated to {minimum}.", "success")
            return redirect(url_for("settings"))
        return render_template(
            "settings.html", active="settings", item_minimum=grocery.item_minimum()
        )

    return app


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A local Flask app to manage grocery inventory")
    parser.add_argument("--port", type=int, default=8888, help="Port to run on local host (default: 8888)")
    args = parser.parse_args()

    app.run(debug=True, port=args.port)
