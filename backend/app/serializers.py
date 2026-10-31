"""Row -> JSON. Three audiences: public, owner, admin. Never include password hashes."""

DEFAULT_EMOJI = {"ICs": "🔲", "Resistors": "〰️", "Boards": "🟩",
                 "Sensors": "📡", "Transistors": "🔌", "Other": "🔧"}


def _image_urls(filenames):
    return [f"/api/images/{f}" for f in (filenames or [])]


def component_public(row, filenames=None):
    tag = row["tag"] or ("Community donation" if row["route"] == "donate" else "Verified")
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "description": row["description"],
        "condition": row["condition"],
        "quantity": row["quantity"],
        "price": row["price"],
        "original_price": row["original_price"] or row["price"],
        "tag": tag,
        "emoji": row["emoji"] or DEFAULT_EMOJI.get(row["category"], "🔧"),
        "route": row["route"],
        "images": _image_urls(filenames),
    }


def component_owner(row, filenames=None):
    d = component_public(row, filenames)
    d.update(status=row["status"], review_note=row["review_note"],
             submitted_at=row["submitted_at"], reviewed_at=row["reviewed_at"])
    return d


def component_admin(row, filenames=None):
    d = component_owner(row, filenames)
    d["submitter"] = ({"id": row["submitted_by"], "name": row["u_name"], "email": row["u_email"],
                       "phone": row["u_phone"], "organization": row["u_org"]}
                      if row["submitted_by"] else None)
    d["approved_at"] = row["approved_at"]
    return d


def user(row):
    return {"id": row["id"], "name": row["name"], "email": row["email"],
            "phone": row["phone"], "organization": row["organization"],
            "created_at": row["created_at"]}


def admin(row):
    from .security import ROLE_PERMISSIONS
    return {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"],
            "permissions": sorted(ROLE_PERMISSIONS.get(row["role"], []))}
