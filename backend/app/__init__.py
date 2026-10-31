"""Application factory."""
from pathlib import Path

from flask import Flask, abort, send_from_directory

from . import db
from .config import load_config
from .errors import register_error_handlers
from .routes import admin, auth, cart, components, images, profile
from .security import csrf_guard

PAGES = {"": "recircuit_frontend.html", "admin": "admin.html"}
STATIC_EXT = {".css", ".js", ".html", ".png", ".jpg", ".svg", ".ico", ".webp"}


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.update(load_config())
    if overrides:
        app.config.update(overrides)

    db.init_db(app.config["DATABASE_PATH"])
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(db.close_db)
    app.before_request(csrf_guard)
    register_error_handlers(app)

    for module in (auth, profile, components, cart, admin, images):
        app.register_blueprint(module.bp)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    # ---- serve the (vanilla) frontend from the same origin -> no CORS needed ----
    @app.get("/", defaults={"page": ""})
    @app.get("/<path:page>")
    def frontend(page):
        root = Path(app.config["FRONTEND_DIR"])
        if page in PAGES:
            page = PAGES[page]
        if Path(page).suffix not in STATIC_EXT:
            abort(404)
        return send_from_directory(root, page)

    return app
