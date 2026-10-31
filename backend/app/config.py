"""Configuration, read from environment variables (optionally a backend/.env file)."""
import logging
import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
ROOT_DIR = BASE_DIR.parent


def _path(name: str, default: str) -> str:
    p = Path(os.getenv(name, default))
    return str(p if p.is_absolute() else (BASE_DIR / p).resolve())


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> dict:
    load_dotenv(BASE_DIR / ".env")
    secret = os.getenv("SECRET_KEY", "")
    if not secret or secret == "change-me":
        logging.warning(
            "SECRET_KEY is not set; using a random key. Sessions will reset on every restart."
        )
        secret = secrets.token_hex(32)
    return {
        "SECRET_KEY": secret,
        "DATABASE_PATH": _path("DATABASE_PATH", "data/recircuit.db"),
        "UPLOAD_DIR": _path("UPLOAD_DIR", "uploads"),
        "FRONTEND_DIR": _path("FRONTEND_DIR", "../frontend"),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": _bool("COOKIE_SECURE"),
        "PERMANENT_SESSION_LIFETIME": timedelta(days=7),
        "ADMIN_SESSION_HOURS": 8,
        "MAX_CONTENT_LENGTH": 8 * 1024 * 1024,  # whole request
        "MAX_IMAGES": 3,
        "MAX_IMAGE_BYTES": 2 * 1024 * 1024,
        "LOGIN_ATTEMPTS": 10,  # per window, per ip+email
        "LOGIN_WINDOW_SECONDS": 15 * 60,
    }
