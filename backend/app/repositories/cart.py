def get_or_create_cart(db, user_id, now):
    row = db.execute("SELECT id FROM carts WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return row["id"]
    return db.execute("INSERT INTO carts (user_id, created_at) VALUES (?,?)", (user_id, now)).lastrowid


def purge_unavailable(db, cart_id):
    """Drop lines whose component is no longer in the global listings."""
    db.execute(
        "DELETE FROM cart_items WHERE cart_id = ? AND component_id NOT IN "
        "(SELECT id FROM global_listings)",
        (cart_id,),
    )


def items(db, cart_id):
    return db.execute(
        """SELECT ci.quantity AS cart_qty, g.*
           FROM cart_items ci JOIN global_listings g ON g.id = ci.component_id
           WHERE ci.cart_id = ? ORDER BY ci.id""",
        (cart_id,),
    ).fetchall()


def get_line(db, cart_id, component_id):
    return db.execute(
        "SELECT * FROM cart_items WHERE cart_id = ? AND component_id = ?", (cart_id, component_id)
    ).fetchone()


def upsert_line(db, cart_id, component_id, quantity):
    db.execute(
        """INSERT INTO cart_items (cart_id, component_id, quantity) VALUES (?,?,?)
           ON CONFLICT(cart_id, component_id) DO UPDATE SET quantity = excluded.quantity""",
        (cart_id, component_id, quantity),
    )


def delete_line(db, cart_id, component_id):
    db.execute("DELETE FROM cart_items WHERE cart_id = ? AND component_id = ?", (cart_id, component_id))


def clear(db, cart_id):
    db.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
