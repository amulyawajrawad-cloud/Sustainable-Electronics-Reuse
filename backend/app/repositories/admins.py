def get(db, admin_id):
    return db.execute("SELECT * FROM admins WHERE id = ?", (admin_id,)).fetchone()


def get_by_email(db, email):
    return db.execute("SELECT * FROM admins WHERE email = ?", (email,)).fetchone()


def create(db, name, email, password_hash, role, now):
    cur = db.execute(
        "INSERT INTO admins (name, email, password_hash, role, created_at) VALUES (?,?,?,?,?)",
        (name, email, password_hash, role, now),
    )
    return cur.lastrowid
