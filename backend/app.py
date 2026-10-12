"""
app.py
Flask entry point.

Run locally (from the repo root):
    flask --app backend.app run --debug
Run in production (Render):
    gunicorn "backend.app:create_app()"
"""

import atexit
import logging
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Flask, jsonify, render_template
from flask.json.provider import DefaultJSONProvider
from jinja2 import TemplateNotFound

from backend.config import Config
from backend.db.mongo import get_mongo, init_mongo
from backend.db.postgres import close_pool, get_cursor, init_pool
from backend.routes import auth, reactions, reveal, walls, wishes
from backend.utils.errors import register_error_handlers
from backend.utils.storage import init_storage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class JSONProvider(DefaultJSONProvider):
    """Return dates as ISO 8601 strings and numbers as numbers."""

    def default(self, o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, timedelta):
            return int(o.total_seconds())
        return super().default(o)


def create_app(overrides=None):
    app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, "frontend", "templates"),
        static_folder=os.path.join(ROOT, "frontend", "static"),
    )
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    app.json = JSONProvider(app)
    app.json.ensure_ascii = False      # send emojis as-is
    logging.basicConfig(level=logging.INFO)

    if app.config["SECRET_KEY"] == "dev-only-change-me" and not app.debug and not app.testing:
        app.logger.warning("SECRET_KEY is not set. Set it in .env before deploying.")

    init_pool(app)
    init_mongo(app)
    init_storage(app)
    atexit.register(close_pool)

    for module in (auth, walls, wishes, reveal, reactions):
        app.register_blueprint(module.bp)
    register_error_handlers(app)

    # -----------------------------------------------------------------
    # Health check: lets you (and Render) see whether both databases work
    # -----------------------------------------------------------------
    @app.get("/api/health")
    def health():
        status = {"postgres": "down", "mongo": "not configured"}
        try:
            with get_cursor() as cur:
                cur.execute("SELECT 1")
            status["postgres"] = "ok"
        except Exception:
            pass
        db = get_mongo()
        if db is not None:
            try:
                db.command("ping")
                status["mongo"] = "ok"
            except Exception:
                status["mongo"] = "down"
        code = 200 if status["postgres"] == "ok" else 503
        return jsonify(status), code

    # -----------------------------------------------------------------
    # HTML pages (frontend/templates). The pages call the JSON API above.
    # -----------------------------------------------------------------
    def page(template, **ctx):
        try:
            return render_template(template, **ctx)
        except TemplateNotFound:
            return (f"<p>Page <code>{template}</code> has not been built yet. "
                    f"The API is running: try <a href='/api/health'>/api/health</a>.</p>"), 501

    @app.get("/")
    def home():
        return page("index.html")

    @app.get("/wall/<token>")
    def contribute_page(token):
        with get_cursor() as cur:
            cur.execute("SELECT 1 FROM walls WHERE contribute_token = %s", (token,))
            exists = cur.fetchone()
        if not exists:
            return page("message.html", title="Link not found",
                        message="This birthday wall link is not valid. Check that you copied the whole link."), 404
        return page("contribute.html", token=token)

    @app.get("/reveal/<token>")
    def reveal_page(token):
        # Decide on the server which page to show, so the wishes page is
        # never even sent before the birthday.
        with get_cursor() as cur:
            cur.execute(
                """SELECT birthday_person_name, reveal_at, now() >= reveal_at AS is_revealed
                     FROM walls WHERE reveal_token = %s""",
                (token,),
            )
            wall = cur.fetchone()
        if wall is None:
            return page("message.html", title="Link not found",
                        message="This birthday wall link is not valid. Check that you copied the whole link."), 404
        if not wall["is_revealed"]:
            return page("countdown.html", token=token,
                        name=wall["birthday_person_name"],
                        reveal_at=wall["reveal_at"].isoformat())
        return page("wall.html", token=token, name=wall["birthday_person_name"])

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
