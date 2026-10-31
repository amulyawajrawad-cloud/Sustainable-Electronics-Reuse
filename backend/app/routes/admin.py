from flask import Blueprint, current_app, jsonify, request

from .. import security, serializers as ser, validation as v
from ..db import get_db
from ..errors import ApiError
from ..repositories import components as repo
from ..repositories import users as user_repo
from ..services import components as service

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/stats")
@security.admin_required()
def stats():
    db = get_db()
    counts = repo.counts_by_status(db)
    return jsonify(**counts, total=sum(counts.values()), users=user_repo.count(db))


@bp.get("/components")
@security.admin_required("review")
def list_components():
    status = v.status_filter(request.args.get("status"))
    limit, offset = v.paging(request.args)
    rows, total = repo.list_admin(get_db(), status, (request.args.get("q") or "").strip() or None,
                                  limit, offset)
    imgs = repo.images_for(get_db(), [r["id"] for r in rows])
    return jsonify(components=[ser.component_admin(r, imgs.get(r["id"])) for r in rows],
                   total=total, limit=limit, offset=offset)


@bp.get("/components/<int:cid>")
@security.admin_required("review")
def get_component(cid):
    row = repo.get_admin(get_db(), cid)
    if not row:
        raise ApiError(404, "not_found", "Component not found.")
    return jsonify(component=ser.component_admin(row, repo.filenames_of(get_db(), cid)))


@bp.post("/components/<int:cid>/approve")
@security.admin_required("review")
def approve(cid):
    note = v.note(request.get_json(silent=True) or {}, "note")
    return jsonify(component=service.review(get_db(), security.current_admin(), cid, "approve", note))


@bp.post("/components/<int:cid>/reject")
@security.admin_required("review")
def reject(cid):
    note = v.note(request.get_json(silent=True) or {}, "reason")
    return jsonify(component=service.review(get_db(), security.current_admin(), cid, "reject", note))


@bp.delete("/components/<int:cid>")
@security.admin_required("manage_listings")
def delete_component(cid):
    service.delete_listing(get_db(), cid, current_app.config)
    return jsonify(ok=True)


@bp.get("/users")
@security.admin_required("view_users")
def list_users():
    limit, offset = v.paging(request.args)
    rows, total = user_repo.list_with_counts(get_db(), (request.args.get("q") or "").strip(),
                                             limit, offset)
    users = [{**ser.user(r), "submissions": r["submissions"], "approved": r["approved"]} for r in rows]
    return jsonify(users=users, total=total, limit=limit, offset=offset)
