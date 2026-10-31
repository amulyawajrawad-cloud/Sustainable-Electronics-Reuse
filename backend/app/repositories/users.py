def get(db, user_id):
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_by_email(db, email):
    return db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def create(db, name, email, password_hash, phone, organization, now):
    cur = db.execute(
        "INSERT INTO users (name, email, password_hash, phone, organization, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (name, email, password_hash, phone, organization, now),
    )
    return cur.lastrowid


def update_profile(db, user_id, name, phone, organization):
    db.execute(
        "UPDATE users SET name=?, phone=?, organization=? WHERE id=?",
        (name, phone, organization, user_id),
    )


def update_password(db, user_id, password_hash):
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id))


def list_with_counts(db, q, limit, offset):
    like = f"%{q}%"
    where, args = ("WHERE u.name LIKE ? OR u.email LIKE ?", [like, like]) if q else ("", [])
    total = db.execute(f"SELECT COUNT(*) FROM users u {where}", args).fetchone()[0]
    rows = db.execute(
        f"""SELECT u.id, u.name, u.email, u.phone, u.organization, u.created_at,
                   (SELECT COUNT(*) FROM components c WHERE c.submitted_by = u.id) AS submissions,
                   (SELECT COUNT(*) FROM components c
                      WHERE c.submitted_by = u.id AND c.status = 'approved') AS approved
            FROM users u {where} ORDER BY u.id DESC LIMIT ? OFFSET ?""",
        [*args, limit, offset],
    ).fetchall()
    return rows, total


def count(db):
    return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
