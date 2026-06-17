"""
main.py — Flask application factory.

Import and call create_app() to get a configured Flask instance.
"""

import logging
import os

from flask import Flask
from flask_cors import CORS

from app.api.routes import bp as api_bp


def create_app() -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__, instance_relative_config=False)

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS(app, resources={r"/*": {"origins": "*"}})

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Register blueprints ───────────────────────────────────────────────────
    app.register_blueprint(api_bp)

    return app
