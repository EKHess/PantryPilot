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

    @app.context_processor
    def store_choices():
        return {"store_choices": grocery.stores()}

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html", active="dashboard", **grocery.dashboard_data())

    @app.get("/inventory")
    def inventory():
        return render_template("inventory.html", active="inventory", items=grocery.inventory_items())

    @app.get("/grocery-lists")
    def grocery_lists():
        return render_template("grocery_lists.html", active="lists", lists=grocery.grocery_lists())

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

    @app.get("/settings")
    def settings():
        return render_template("placeholder.html", active="settings", title="Settings", subtitle="Customize PantryPilot for your household.")

    return app


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A local Flask app to manage grocery inventory")
    parser.add_argument("--port", type=int, default=8888, help="Port to run on local host (default: 8888)")
    args = parser.parse_args()

    app.run(debug=True, port=args.port)
