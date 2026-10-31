"""CLI:  python manage.py init-db | seed [--no-demo] | create-admin | run"""
import argparse
import getpass
import os
import sys

from app import create_app
from app.db import connect, init_db, now_iso
from app.repositories import admins as admin_repo
from app.repositories import components as comp_repo
from app.security import hash_password

DEMO_COMPONENTS = [
    ("NE555 Timer IC", "ICs", "🔲", 12, 20, "Excellent", "Popular", "Timer and oscillator IC", 25),
    ("Resistor Assortment (20 pcs)", "Resistors", "〰️", 18, 30, "Good", "Bundle", "Mixed values for prototyping", 15),
    ("Arduino Uno Compatible", "Boards", "🟩", 180, 350, "Excellent", "Verified", "Microcontroller development board", 6),
    ("HC-SR04 Ultrasonic Sensor", "Sensors", "📡", 45, 80, "Good", "Tested", "Distance measurement sensor", 12),
    ("BC547 Transistor (10 pcs)", "Transistors", "🔌", 15, 25, "Excellent", "Bundle", "General-purpose NPN transistor", 30),
    ("Breadboard 400 points", "Boards", "▦", 35, 60, "Good", "Student pick", "Solderless prototyping board", 10),
    ("LM358 Op-Amp IC", "ICs", "🔳", 10, 18, "Excellent", "Verified", "Dual operational amplifier", 20),
    ("DHT11 Temperature Sensor", "Sensors", "🌡️", 55, 95, "Good", "Tested", "Temperature and humidity module", 8),
]


def create_admin(path, name, email, password, role="super_admin"):
    conn = connect(path)
    try:
        if admin_repo.get_by_email(conn, email):
            print(f"Admin {email} already exists - skipped.")
            return None
        with conn:
            aid = admin_repo.create(conn, name, email.lower(), hash_password(password), role, now_iso())
        print(f"Created {role} admin {email}")
        return aid
    finally:
        conn.close()


def seed(path, demo=True):
    """Minimum data for a demo: one super admin (from env) + starter listings."""
    email = os.getenv("ADMIN_EMAIL", "admin@recircuit.local")
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        sys.exit("Set ADMIN_PASSWORD (in backend/.env) before seeding.")
    create_admin(path, os.getenv("ADMIN_NAME", "Site Admin"), email, password)
    if not demo:
        return
    conn = connect(path)
    try:
        if conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]:
            print("Components already present - demo listings skipped.")
            return
        admin_id = admin_repo.get_by_email(conn, email.lower())["id"]
        with conn:
            for n, cat, emoji, price, old, cond, tag, desc, qty in DEMO_COMPONENTS:
                comp_repo.insert_seed(conn, dict(name=n, category=cat, emoji=emoji, price=price,
                                                 original_price=old, condition=cond, tag=tag,
                                                 description=desc, quantity=qty), admin_id, now_iso())
        print(f"Seeded {len(DEMO_COMPONENTS)} starter listings.")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    s = sub.add_parser("seed"); s.add_argument("--no-demo", action="store_true")
    c = sub.add_parser("create-admin")
    c.add_argument("--name", required=True); c.add_argument("--email", required=True)
    c.add_argument("--role", choices=["super_admin", "reviewer"], default="reviewer")
    sub.add_parser("run")
    args = ap.parse_args()

    app = create_app()
    path = app.config["DATABASE_PATH"]
    if args.cmd == "init-db":
        init_db(path); print("Database ready:", path)
    elif args.cmd == "seed":
        seed(path, demo=not args.no_demo)
    elif args.cmd == "create-admin":
        pw = getpass.getpass("Password (min 8 chars): ")
        if len(pw) < 8:
            sys.exit("Password too short.")
        create_admin(path, args.name, args.email, pw, args.role)
    elif args.cmd == "run":
        app.run(host="127.0.0.1", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG") == "1")


if __name__ == "__main__":
    main()
