import sqlite3

from flask import Blueprint, jsonify, request, session

from .. import security, serializers as ser, validation as v
from ..db import get_db, now_iso
from ..errors import ApiError
from ..repositories import admins as admin_repo
from ..repositories import users as user_repo

bp = Blueprint("auth", __name__, url_prefix="/api")


def _json():
    return request.get_json(silent=True) or {}


# ---------------------------------------------------------------- users
@bp.post("/auth/register")
def register():
    clean = v.registration(_json())
    db = get_db()
    try:
        with db:
            uid = user_repo.create(db, clean["name"], clean["email"],
                                   security.hash_password(clean["password"]),
                                   clean["phone"], clean["organization"], now_iso())
    except sqlite3.IntegrityError:
        raise ApiError(409, "email_taken", "An account with this email already exists.",
                       {"email": "Already registered."})
    session["user_id"] = uid
    session.permanent = True
    return jsonify(user=ser.user(user_repo.get(db, uid))), 201


@bp.post("/auth/login")
def login():
    email, password = v.login(_json())
    key = f"user:{request.remote_addr}:{email}"
    security.rate_limit(key)
    row = user_repo.get_by_email(get_db(), email)
    if not security.verify_password(row["password_hash"] if row else None, password):
        raise ApiError(401, "invalid_credentials", "Incorrect email or password.")
    security.rate_limit_reset(key)
    session["user_id"] = row["id"]
    session.permanent = True
    return jsonify(user=ser.user(row))


@bp.post("/auth/logout")
def logout():
    session.pop("user_id", None)
    return jsonify(ok=True)


@bp.get("/auth/me")
def me():
    u = security.current_user()
    return jsonify(user=ser.user(u) if u else None)


# ---------------------------------------------------------------- admins (separate login)
@bp.post("/admin/auth/login")
def admin_login():
    email, password = v.login(_json())
    key = f"admin:{request.remote_addr}:{email}"
    security.rate_limit(key)
    row = admin_repo.get_by_email(get_db(), email)
    if not security.verify_password(row["password_hash"] if row else None, password):
        raise ApiError(401, "invalid_credentials", "Incorrect email or password.")
    security.rate_limit_reset(key)
    import time
    session["admin_id"] = row["id"]
    session["admin_at"] = time.time()
    return jsonify(admin=ser.admin(row))


@bp.post("/admin/auth/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_at", None)
    return jsonify(ok=True)


@bp.get("/admin/auth/me")
def admin_me():
    a = security.current_admin()
    return jsonify(admin=ser.admin(a) if a else None)
