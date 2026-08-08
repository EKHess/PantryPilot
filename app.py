"""PantryPilot Flask application entrypoint."""

from flask import Flask, render_template
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

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html", active="dashboard", **grocery.dashboard_data())

    @app.get("/inventory")
    def inventory():
        return render_template("inventory.html", active="inventory", items=grocery.inventory_items())

    @app.get("/grocery-lists")
    def grocery_lists():
        return render_template("grocery_lists.html", active="lists", lists=grocery.grocery_lists())

    @app.get("/stores")
    def stores():
        return render_template("placeholder.html", active="stores", title="Stores", subtitle="Manage the places where you shop.")

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
