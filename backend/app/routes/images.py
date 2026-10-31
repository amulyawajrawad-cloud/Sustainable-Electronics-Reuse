import re
from pathlib import Path

from flask import Blueprint, abort, current_app, send_from_directory

from .. import security
from ..db import get_db
from ..repositories import components as repo
from ..services.images import MIME

bp = Blueprint("images", __name__, url_prefix="/api")
NAME_RE = re.compile(r"^[0-9a-f]{32}\.(png|jpg|gif|webp)$")


@bp.get("/images/<filename>")
def image(filename):
    """Images of live listings are public; images of pending/rejected ones are visible only
    to their owner and to admins."""
    if not NAME_RE.match(filename):
        abort(404)
    info = repo.image_owner_info(get_db(), filename)
    if not info:
        abort(404)
    is_public = info["status"] == "approved" and info["route"] != "recycle" and info["condition"] != "Defective"
    user = security.current_user()
    allowed = is_public or security.current_admin() or (user and user["id"] == info["submitted_by"])
    if not allowed:
        abort(404)
    resp = send_from_directory(Path(current_app.config["UPLOAD_DIR"]), filename,
                               mimetype=MIME[filename.rsplit(".", 1)[1]])
    resp.headers["Cache-Control"] = "public, max-age=3600" if is_public else "private, no-store"
    return resp
