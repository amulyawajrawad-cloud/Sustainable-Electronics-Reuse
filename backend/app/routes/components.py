from flask import Blueprint, current_app, jsonify, request

from .. import security, serializers as ser
from ..db import get_db
from ..errors import ApiError
from ..repositories import components as repo
from ..services import components as service

bp = Blueprint("components", __name__, url_prefix="/api")


@bp.get("/components")
def list_global():
    """Public global listings: approved components only (reads the global_listings view)."""
    a = request.args
    rows = repo.list_public(get_db(), a.get("category"), a.get("condition"),
                            (a.get("q") or "").strip() or None, a.get("sort", "featured"))
    imgs = repo.images_for(get_db(), [r["id"] for r in rows])
    return jsonify(components=[ser.component_public(r, imgs.get(r["id"])) for r in rows])


@bp.get("/components/<int:cid>")
def get_global(cid):
    row = repo.get_public(get_db(), cid)
    if not row:
        raise ApiError(404, "not_found", "Component not found.")
    return jsonify(component=ser.component_public(row, repo.filenames_of(get_db(), cid)))


@bp.post("/components")
@security.login_required
def submit():
    if request.mimetype == "multipart/form-data":
        data, files = request.form.to_dict(), request.files.getlist("images")
    else:
        data, files = request.get_json(silent=True) or {}, []
    comp = service.submit(get_db(), security.current_user(), data, files, current_app.config)
    return jsonify(component=comp), 201


@bp.get("/my/components")
@security.login_required
def my_components():
    return jsonify(components=service.list_mine(get_db(), security.current_user()))


@bp.delete("/my/components/<int:cid>")
@security.login_required
def withdraw(cid):
    service.withdraw(get_db(), security.current_user(), cid, current_app.config)
    return jsonify(ok=True)
