"""Business rules for the submission -> review -> publish workflow."""
from .. import serializers as ser
from .. import validation as v
from ..db import now_iso
from ..errors import ApiError
from ..repositories import components as repo
from ..security import admin_can
from . import images


def submit(db, user, data, files, cfg):
    """A user submits a component. It is always saved as 'pending' (never public)."""
    clean = v.component(data)
    names = images.save_images(files, cfg)
    try:
        with db:
            now = now_iso()
            cid = repo.create(db, user["id"], clean, now)
            repo.add_images(db, cid, names, now)
    except Exception:
        images.delete_files(names, cfg)
        raise
    return ser.component_owner(repo.get(db, cid), names)


def list_mine(db, user):
    rows = repo.list_by_user(db, user["id"])
    imgs = repo.images_for(db, [r["id"] for r in rows])
    return [ser.component_owner(r, imgs.get(r["id"])) for r in rows]


def withdraw(db, user, component_id, cfg):
    """Owners may withdraw their own submission unless it is live in the marketplace."""
    row = repo.get(db, component_id)
    if not row or row["submitted_by"] != user["id"]:
        raise ApiError(404, "not_found", "Submission not found.")  # 404, don't leak existence
    if row["status"] == "approved":
        raise ApiError(409, "conflict", "Live listings can only be removed by an admin.")
    names = repo.filenames_of(db, component_id)
    with db:
        repo.delete(db, component_id)
    images.delete_files(names, cfg)


def review(db, admin, component_id, action, note):
    """Approve/reject. Reviewers act on pending items; re-opening or taking down an already
    reviewed item needs the `manage_listings` permission (super_admin)."""
    row = repo.get(db, component_id)
    if not row:
        raise ApiError(404, "not_found", "Component not found.")
    if row["status"] != "pending" and not admin_can(admin, "manage_listings"):
        raise ApiError(403, "forbidden", "Only a super admin can change an already-reviewed listing.")
    target = {"approve": "approved", "reject": "rejected"}[action]
    if row["status"] == target:
        raise ApiError(409, "conflict", f"Component is already {target}.")
    with db:
        repo.set_review(db, component_id, target, admin["id"], note, now_iso())
    return ser.component_admin(repo.get_admin(db, component_id), repo.filenames_of(db, component_id))


def delete_listing(db, component_id, cfg):
    row = repo.get(db, component_id)
    if not row:
        raise ApiError(404, "not_found", "Component not found.")
    names = repo.filenames_of(db, component_id)
    with db:
        repo.delete(db, component_id)
    images.delete_files(names, cfg)
