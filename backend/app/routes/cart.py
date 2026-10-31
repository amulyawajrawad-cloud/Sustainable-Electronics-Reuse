from flask import Blueprint, jsonify, request

from .. import security
from ..db import get_db
from ..errors import ApiError
from ..services import cart as service

bp = Blueprint("cart", __name__, url_prefix="/api/cart")


def _qty(data, key="quantity", *, allow_zero=False, default=None):
    raw = data.get(key, default)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        raise ApiError(400, "validation_error", "quantity must be a whole number.")
    if n < (0 if allow_zero else 1) or n > service.MAX_LINE_QTY:
        raise ApiError(400, "validation_error", f"quantity must be 1-{service.MAX_LINE_QTY}.")
    return n


@bp.get("")
@security.login_required
def get_cart():
    return jsonify(service.view(get_db(), security.current_user()))


@bp.post("/items")
@security.login_required
def add_item():
    data = request.get_json(silent=True) or {}
    try:
        cid = int(data.get("component_id"))
    except (TypeError, ValueError):
        raise ApiError(400, "validation_error", "component_id is required.")
    return jsonify(service.add(get_db(), security.current_user(), cid, _qty(data, default=1)))


@bp.patch("/items/<int:cid>")
@security.login_required
def update_item(cid):
    data = request.get_json(silent=True) or {}
    return jsonify(service.set_quantity(get_db(), security.current_user(), cid,
                                        _qty(data, allow_zero=True)))


@bp.delete("/items/<int:cid>")
@security.login_required
def remove_item(cid):
    return jsonify(service.remove(get_db(), security.current_user(), cid))


@bp.delete("")
@security.login_required
def clear_cart():
    return jsonify(service.clear(get_db(), security.current_user()))
