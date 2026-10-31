"""Authentication helpers, role-based permissions, CSRF guard and a tiny rate limiter."""
import time
from collections import defaultdict, deque
from functools import wraps

from flask import current_app, g, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .errors import ApiError
from .repositories import admins as admin_repo
from .repositories import users as user_repo

# ---- roles -> permissions -------------------------------------------------
ROLE_PERMISSIONS = {
    "reviewer": {"review", "view_users"},
    "super_admin": {"review", "view_users", "manage_listings"},
}


def admin_can(admin, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(admin["role"], set())


# ---- passwords ------------------------------------------------------------
def hash_password(pw: str) -> str:
    return generate_password_hash(pw)  # scrypt + per-password salt


_DUMMY_HASH = generate_password_hash("not-a-real-password")


def verify_password(stored_hash, pw: str) -> bool:
    # Always run a hash check so "unknown email" and "wrong password" take similar time.
    return check_password_hash(stored_hash or _DUMMY_HASH, pw) and stored_hash is not None


# ---- current principal ----------------------------------------------------
def current_user():
    if "current_user" not in g:
        uid = session.get("user_id")
        g.current_user = user_repo.get(get_db(), uid) if uid else None
    return g.current_user


def current_admin():
    if "current_admin" not in g:
        g.current_admin = None
        aid, at = session.get("admin_id"), session.get("admin_at", 0)
        if aid and time.time() - at < current_app.config["ADMIN_SESSION_HOURS"] * 3600:
            g.current_admin = admin_repo.get(get_db(), aid)
    return g.current_admin


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            raise ApiError(401, "auth_required", "Please log in to continue.")
        return fn(*a, **kw)

    return wrapper


def admin_required(permission: str | None = None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            admin = current_admin()
            if not admin:
                raise ApiError(401, "admin_auth_required", "Admin login required.")
            if permission and not admin_can(admin, permission):
                raise ApiError(403, "forbidden", "Your admin role cannot do this.")
            return fn(*a, **kw)

        return wrapper

    return deco


# ---- CSRF: state-changing API calls must carry a custom header -------------
# Browsers cannot add custom headers cross-site without a CORS preflight (which we
# never allow), and cookies are SameSite=Lax. Together this blocks cross-site forgery.
def csrf_guard():
    if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("X-Requested-With") != "recircuit":
            raise ApiError(403, "csrf", "Missing X-Requested-With header.")


# ---- naive in-memory rate limiter (fine for one process; use Redis to scale) ----
_attempts: dict[str, deque] = defaultdict(deque)


def rate_limit(key: str) -> None:
    cfg = current_app.config
    now, window = time.time(), cfg["LOGIN_WINDOW_SECONDS"]
    q = _attempts[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= cfg["LOGIN_ATTEMPTS"]:
        raise ApiError(429, "too_many_attempts", "Too many attempts. Please try again later.")
    q.append(now)


def rate_limit_reset(key: str) -> None:
    _attempts.pop(key, None)
