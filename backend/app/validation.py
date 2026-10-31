"""Input validation. Each validator returns clean data or raises ApiError(400, fields=...)."""
import re

from .errors import ApiError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CATEGORIES = ("ICs", "Resistors", "Boards", "Sensors", "Transistors", "Other")
CONDITIONS = ("Excellent", "Good", "Defective")
ROUTES = ("sell", "donate", "recycle")
STATUSES = ("pending", "approved", "rejected")


def _fail(fields):
    raise ApiError(400, "validation_error", "Please fix the highlighted fields.", fields)


def _str(data, key, errors, *, min_len=0, max_len=200, required=False, label=None):
    label = label or key
    val = data.get(key)
    val = "" if val is None else str(val).strip()
    if required and not val:
        errors[key] = f"{label} is required."
    elif val and len(val) < min_len:
        errors[key] = f"{label} must be at least {min_len} characters."
    elif len(val) > max_len:
        errors[key] = f"{label} must be at most {max_len} characters."
    return val


def _int(data, key, errors, *, lo, hi, label, required=True, default=None):
    raw = data.get(key)
    if raw in (None, ""):
        if required and default is None:
            errors[key] = f"{label} is required."
            return None
        return default
    try:
        if isinstance(raw, bool) or (isinstance(raw, float) and raw != int(raw)):
            raise ValueError
        n = int(str(raw).strip())
    except (ValueError, TypeError):
        errors[key] = f"{label} must be a whole number."
        return None
    if not lo <= n <= hi:
        errors[key] = f"{label} must be between {lo} and {hi}."
        return None
    return n


def _email(data, errors):
    email = _str(data, "email", errors, required=True, max_len=254, label="Email").lower()
    if email and "email" not in errors and not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    return email


def _password(data, key, errors, label="Password"):
    pw = data.get(key)
    pw = "" if pw is None else str(pw)
    if len(pw) < 8:
        errors[key] = f"{label} must be at least 8 characters."
    elif len(pw) > 128:
        errors[key] = f"{label} must be at most 128 characters."
    return pw


def registration(data):
    e = {}
    out = {
        "name": _str(data, "name", e, min_len=2, max_len=80, required=True, label="Name"),
        "email": _email(data, e),
        "password": _password(data, "password", e),
        "phone": _str(data, "phone", e, max_len=20, label="Phone") or None,
        "organization": _str(data, "organization", e, max_len=100, label="College / organization") or None,
    }
    if e:
        _fail(e)
    return out


def login(data):
    email = str(data.get("email") or "").strip().lower()
    pw = str(data.get("password") or "")
    if not email or not pw:
        _fail({"email" if not email else "password": "Required."})
    return email, pw


def profile(data):
    e = {}
    out = {
        "name": _str(data, "name", e, min_len=2, max_len=80, required=True, label="Name"),
        "phone": _str(data, "phone", e, max_len=20, label="Phone") or None,
        "organization": _str(data, "organization", e, max_len=100, label="College / organization") or None,
    }
    if e:
        _fail(e)
    return out


def password_change(data):
    e = {}
    current = str(data.get("current_password") or "")
    if not current:
        e["current_password"] = "Current password is required."
    new = _password(data, "new_password", e, "New password")
    if e:
        _fail(e)
    return current, new


def component(data):
    e = {}
    out = {
        "name": _str(data, "name", e, min_len=2, max_len=120, required=True, label="Component name"),
        "description": _str(data, "description", e, max_len=1000, label="Notes"),
        "quantity": _int(data, "quantity", e, lo=1, hi=10000, label="Quantity"),
        "price": _int(data, "price", e, lo=0, hi=1_000_000, label="Price", default=0),
        "original_price": _int(data, "original_price", e, lo=0, hi=1_000_000,
                               label="Original price", required=False),
    }
    for key, allowed, label in (("category", CATEGORIES, "Category"),
                                ("condition", CONDITIONS, "Condition"),
                                ("route", ROUTES, "Option")):
        val = str(data.get(key) or ("sell" if key == "route" else "")).strip()
        if val not in allowed:
            e[key] = f"{label} must be one of: {', '.join(allowed)}."
        out[key] = val
    if e:
        _fail(e)
    # Business rules: defective parts can only be routed to recycling; donations are free.
    if out["condition"] == "Defective":
        out["route"] = "recycle"
    if out["route"] in ("donate", "recycle"):
        out["price"] = 0
    if out["original_price"] is not None and out["original_price"] < out["price"]:
        out["original_price"] = None
    return out


def note(data, key="note", max_len=500):
    e = {}
    val = _str(data, key, e, max_len=max_len, label="Note")
    if e:
        _fail(e)
    return val or None


def status_filter(value):
    if value in (None, "", "all"):
        return None
    if value not in STATUSES:
        raise ApiError(400, "validation_error", f"status must be one of: {', '.join(STATUSES)}.")
    return value


def paging(args, default=50, maximum=100):
    try:
        limit = min(max(int(args.get("limit", default)), 1), maximum)
        offset = max(int(args.get("offset", 0)), 0)
    except ValueError:
        raise ApiError(400, "validation_error", "limit and offset must be integers.")
    return limit, offset
