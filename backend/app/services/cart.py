"""Cart rules: only globally-listed components, never your own, never more than stock."""
from .. import serializers as ser
from ..db import now_iso
from ..errors import ApiError
from ..repositories import cart as repo
from ..repositories import components as comp_repo

MAX_LINE_QTY = 99


def view(db, user):
    with db:
        cart_id = repo.get_or_create_cart(db, user["id"], now_iso())
        repo.purge_unavailable(db, cart_id)
    rows = repo.items(db, cart_id)
    imgs = comp_repo.images_for(db, [r["id"] for r in rows])
    lines = [{"component": ser.component_public(r, imgs.get(r["id"])), "quantity": r["cart_qty"]}
             for r in rows]
    return {
        "items": lines,
        "count": sum(l["quantity"] for l in lines),
        "total": sum(l["quantity"] * l["component"]["price"] for l in lines),
    }


def _check_qty(component, qty):
    limit = min(component["quantity"], MAX_LINE_QTY)
    if qty > limit:
        raise ApiError(409, "insufficient_stock", f"Only {limit} available.")


def add(db, user, component_id, qty):
    comp = comp_repo.get_public(db, component_id)
    if not comp:
        raise ApiError(404, "not_found", "This component is not available.")
    if comp["submitted_by"] == user["id"]:
        raise ApiError(400, "own_listing", "You can't add your own listing to your cart.")
    with db:
        cart_id = repo.get_or_create_cart(db, user["id"], now_iso())
        line = repo.get_line(db, cart_id, component_id)
        new_qty = (line["quantity"] if line else 0) + qty
        _check_qty(comp, new_qty)
        repo.upsert_line(db, cart_id, component_id, new_qty)
    return view(db, user)


def set_quantity(db, user, component_id, qty):
    with db:
        cart_id = repo.get_or_create_cart(db, user["id"], now_iso())
        if qty == 0:
            repo.delete_line(db, cart_id, component_id)
        else:
            comp = comp_repo.get_public(db, component_id)
            if not comp or not repo.get_line(db, cart_id, component_id):
                raise ApiError(404, "not_found", "Item is not in your cart.")
            _check_qty(comp, qty)
            repo.upsert_line(db, cart_id, component_id, qty)
    return view(db, user)


def remove(db, user, component_id):
    return set_quantity(db, user, component_id, 0)


def clear(db, user):
    with db:
        repo.clear(db, repo.get_or_create_cart(db, user["id"], now_iso()))
    return view(db, user)
