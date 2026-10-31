from flask import Blueprint, jsonify, request

from .. import security, serializers as ser, validation as v
from ..db import get_db
from ..errors import ApiError
from ..repositories import users as user_repo

bp = Blueprint("profile", __name__, url_prefix="/api/profile")


@bp.get("")
@security.login_required
def get_profile():
    return jsonify(user=ser.user(security.current_user()))


@bp.put("")
@security.login_required
def update_profile():
    clean = v.profile(request.get_json(silent=True) or {})
    db, user = get_db(), security.current_user()
    with db:  # always the logged-in user's own row; no user id is ever taken from the client
        user_repo.update_profile(db, user["id"], clean["name"], clean["phone"], clean["organization"])
    return jsonify(user=ser.user(user_repo.get(db, user["id"])))


@bp.put("/password")
@security.login_required
def change_password():
    current, new = v.password_change(request.get_json(silent=True) or {})
    db, user = get_db(), security.current_user()
    if not security.verify_password(user["password_hash"], current):
        raise ApiError(400, "validation_error", "Current password is incorrect.",
                       {"current_password": "Incorrect password."})
    with db:
        user_repo.update_password(db, user["id"], security.hash_password(new))
    return jsonify(ok=True)
