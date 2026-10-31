"""All SQL for components + images. Public reads go through the `global_listings` view."""

SORTS = {
    "featured": "id ASC",
    "low": "price ASC, id ASC",
    "high": "price DESC, id ASC",
    "newest": "approved_at DESC, id DESC",
}


def create(db, user_id, d, now):
    cur = db.execute(
        """INSERT INTO components
           (name, category, description, condition, quantity, price, original_price,
            route, status, submitted_by, submitted_at)
           VALUES (?,?,?,?,?,?,?,?, 'pending', ?, ?)""",
        (d["name"], d["category"], d["description"], d["condition"], d["quantity"],
         d["price"], d.get("original_price"), d["route"], user_id, now),
    )
    return cur.lastrowid


def insert_seed(db, d, admin_id, now):
    cur = db.execute(
        """INSERT INTO components
           (name, category, description, condition, quantity, price, original_price, tag, emoji,
            route, status, reviewed_by, submitted_at, reviewed_at, approved_at)
           VALUES (?,?,?,?,?,?,?,?,?, 'sell', 'approved', ?, ?, ?, ?)""",
        (d["name"], d["category"], d["description"], d["condition"], d["quantity"], d["price"],
         d["original_price"], d["tag"], d["emoji"], admin_id, now, now, now),
    )
    return cur.lastrowid


def get(db, component_id):
    return db.execute("SELECT * FROM components WHERE id = ?", (component_id,)).fetchone()


def get_public(db, component_id):
    return db.execute("SELECT * FROM global_listings WHERE id = ?", (component_id,)).fetchone()


def list_public(db, category=None, condition=None, q=None, sort="featured"):
    where, args = [], []
    if category and category != "All":
        where.append("category = ?"); args.append(category)
    if condition and condition != "all":
        where.append("condition = ?"); args.append(condition)
    if q:
        where.append("(name LIKE ? OR category LIKE ? OR description LIKE ?)")
        args += [f"%{q}%"] * 3
    sql = "SELECT * FROM global_listings"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY " + SORTS.get(sort, SORTS["featured"])
    return db.execute(sql, args).fetchall()


def list_by_user(db, user_id):
    return db.execute(
        "SELECT * FROM components WHERE submitted_by = ? ORDER BY id DESC", (user_id,)
    ).fetchall()


def list_admin(db, status, q, limit, offset):
    where, args = [], []
    if status:
        where.append("c.status = ?"); args.append(status)
    if q:
        where.append("(c.name LIKE ? OR u.name LIKE ? OR u.email LIKE ?)")
        args += [f"%{q}%"] * 3
    w = ("WHERE " + " AND ".join(where)) if where else ""
    base = f"FROM components c LEFT JOIN users u ON u.id = c.submitted_by {w}"
    total = db.execute(f"SELECT COUNT(*) {base}", args).fetchone()[0]
    rows = db.execute(
        f"""SELECT c.*, u.name AS u_name, u.email AS u_email, u.phone AS u_phone,
                   u.organization AS u_org
            {base} ORDER BY (c.status = 'pending') DESC, c.id DESC LIMIT ? OFFSET ?""",
        [*args, limit, offset],
    ).fetchall()
    return rows, total


def get_admin(db, component_id):
    return db.execute(
        """SELECT c.*, u.name AS u_name, u.email AS u_email, u.phone AS u_phone,
                  u.organization AS u_org
           FROM components c LEFT JOIN users u ON u.id = c.submitted_by WHERE c.id = ?""",
        (component_id,),
    ).fetchone()


def counts_by_status(db):
    rows = db.execute("SELECT status, COUNT(*) n FROM components GROUP BY status").fetchall()
    out = {"pending": 0, "approved": 0, "rejected": 0}
    out.update({r["status"]: r["n"] for r in rows})
    return out


def set_review(db, component_id, status, admin_id, note, now):
    db.execute(
        """UPDATE components SET status=?, reviewed_by=?, review_note=?, reviewed_at=?,
               approved_at = CASE WHEN ? = 'approved' THEN ? ELSE NULL END
           WHERE id=?""",
        (status, admin_id, note, now, status, now, component_id),
    )


def delete(db, component_id):
    db.execute("DELETE FROM components WHERE id = ?", (component_id,))


# ---- images -----------------------------------------------------------------
def add_images(db, component_id, filenames, now):
    db.executemany(
        "INSERT INTO component_images (component_id, filename, created_at) VALUES (?,?,?)",
        [(component_id, f, now) for f in filenames],
    )


def images_for(db, component_ids):
    if not component_ids:
        return {}
    marks = ",".join("?" * len(component_ids))
    rows = db.execute(
        f"SELECT component_id, filename FROM component_images "
        f"WHERE component_id IN ({marks}) ORDER BY id",
        list(component_ids),
    ).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["component_id"], []).append(r["filename"])
    return out


def filenames_of(db, component_id):
    return [r["filename"] for r in db.execute(
        "SELECT filename FROM component_images WHERE component_id = ?", (component_id,))]


def image_owner_info(db, filename):
    return db.execute(
        """SELECT c.id, c.submitted_by, c.status, c.route, c.condition
           FROM component_images i JOIN components c ON c.id = i.component_id
           WHERE i.filename = ?""",
        (filename,),
    ).fetchone()
