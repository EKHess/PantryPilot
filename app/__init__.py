import os
from flask import Flask, jsonify, render_template, request

from . import db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("PANTRYPILOT_SECRET_KEY", "dev-change-me"),
        DATABASE=os.path.join(app.instance_path, "pantrypilot.sqlite3"),
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)

    from .dashboard.routes import bp as dashboard_bp
    from .inventory.routes import bp as inventory_bp
    from .stores.routes import bp as stores_bp
    from .settings.routes import bp as settings_bp
    from .grocery_lists.routes import bp as lists_bp
    for blueprint in (dashboard_bp, inventory_bp, stores_bp, settings_bp, lists_bp):
        app.register_blueprint(blueprint)

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify(error={"code": "not_found", "message": "Resource not found."}), 404
        return render_template("errors/404.html"), 404

    return app

