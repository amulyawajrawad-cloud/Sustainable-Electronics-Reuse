"""End-to-end API tests incl. the Definition-of-Done scenario. Run: python -m unittest -v"""
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import create_app  # noqa: E402
from app.db import connect, now_iso  # noqa: E402
from app.repositories import admins  # noqa: E402
from app.security import hash_password  # noqa: E402

H = {"X-Requested-With": "recircuit"}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({"TESTING": True, "SECRET_KEY": "t", "DATABASE_PATH": f"{self.tmp}/t.db",
                               "UPLOAD_DIR": f"{self.tmp}/up", "LOGIN_ATTEMPTS": 5})
        c = connect(self.app.config["DATABASE_PATH"])
        with c:
            admins.create(c, "Root", "root@x.io", hash_password("rootpass123"), "super_admin", now_iso())
            admins.create(c, "Rev", "rev@x.io", hash_password("revpass1234"), "reviewer", now_iso())
        c.close()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def client(self):
        return self.app.test_client()

    def user(self, name="alice"):
        c = self.client()
        r = c.post("/api/auth/register", headers=H, json={"name": name.title(), "email": f"{name}@x.io",
                                                          "password": "password123"})
        self.assertEqual(r.status_code, 201, r.json)
        return c

    def admin(self, email="root@x.io", pw="rootpass123"):
        c = self.client()
        r = c.post("/api/admin/auth/login", headers=H, json={"email": email, "password": pw})
        self.assertEqual(r.status_code, 200, r.json)
        return c

    def submit(self, c, **kw):
        d = dict(name="Test Part", category="ICs", condition="Good", quantity=3, price=20, route="sell")
        d.update(kw)
        r = c.post("/api/components", headers=H, json=d)
        self.assertEqual(r.status_code, 201, r.json)
        return r.json["component"]


class DefinitionOfDone(Base):
    def test_full_flow(self):
        alice, bob = self.user("alice"), self.user("bob")
        comp = self.submit(alice, name="Op-Amp")
        self.assertEqual(comp["status"], "pending")
        # pending not public (list, detail, anonymous and other user)
        for c in (self.client(), bob):
            self.assertEqual(c.get("/api/components").json["components"], [])
            self.assertEqual(c.get(f"/api/components/{comp['id']}").status_code, 404)
        # admin sees it and approves
        adm = self.admin()
        self.assertEqual(adm.get("/api/admin/stats").json["pending"], 1)
        lst = adm.get("/api/admin/components?status=pending").json
        self.assertEqual(lst["total"], 1)
        self.assertEqual(lst["components"][0]["submitter"]["email"], "alice@x.io")
        r = adm.post(f"/api/admin/components/{comp['id']}/approve", headers=H, json={"note": "Looks good"})
        self.assertEqual(r.json["component"]["status"], "approved")
        # visible to everyone; bob adds to cart
        self.assertEqual(len(self.client().get("/api/components").json["components"]), 1)
        r = bob.post("/api/cart/items", headers=H, json={"component_id": comp["id"], "quantity": 2})
        self.assertEqual(r.json["count"], 2); self.assertEqual(r.json["total"], 40)
        # alice sees review status + note
        mine = alice.get("/api/my/components").json["components"][0]
        self.assertEqual((mine["status"], mine["review_note"]), ("approved", "Looks good"))

    def test_reject_stays_hidden(self):
        alice = self.user(); comp = self.submit(alice)
        adm = self.admin("rev@x.io", "revpass1234")
        r = adm.post(f"/api/admin/components/{comp['id']}/reject", headers=H, json={"reason": "Blurry"})
        self.assertEqual(r.json["component"]["status"], "rejected")
        self.assertEqual(self.client().get("/api/components").json["components"], [])
        self.assertEqual(alice.get("/api/my/components").json["components"][0]["review_note"], "Blurry")
        self.assertEqual(adm.get("/api/admin/stats").json["rejected"], 1)


class Security(Base):
    def test_user_cannot_use_admin_api(self):
        u = self.user()
        for path in ("/api/admin/stats", "/api/admin/components", "/api/admin/users"):
            self.assertEqual(u.get(path).status_code, 401)
        comp = self.submit(u)
        self.assertEqual(u.post(f"/api/admin/components/{comp['id']}/approve", headers=H, json={}).status_code, 401)

    def test_user_login_is_not_admin_login(self):
        c = self.client()
        r = c.post("/api/admin/auth/login", headers=H, json={"email": "alice@x.io", "password": "password123"})
        self.assertEqual(r.status_code, 401)

    def test_reviewer_permissions(self):
        u = self.user(); comp = self.submit(u)
        rev = self.admin("rev@x.io", "revpass1234")
        self.assertEqual(rev.get("/api/admin/users").status_code, 200)
        rev.post(f"/api/admin/components/{comp['id']}/approve", headers=H, json={})
        # reviewer can't take down / delete reviewed listings
        self.assertEqual(rev.post(f"/api/admin/components/{comp['id']}/reject", headers=H, json={}).status_code, 403)
        self.assertEqual(rev.delete(f"/api/admin/components/{comp['id']}", headers=H).status_code, 403)
        root = self.admin()
        self.assertEqual(root.post(f"/api/admin/components/{comp['id']}/reject", headers=H, json={"reason": "x"}).status_code, 200)
        self.assertEqual(root.delete(f"/api/admin/components/{comp['id']}", headers=H).status_code, 200)

    def test_ownership(self):
        alice, bob = self.user("alice"), self.user("bob")
        comp = self.submit(alice)
        self.assertEqual(bob.delete(f"/api/my/components/{comp['id']}", headers=H).status_code, 404)
        self.assertEqual(bob.get("/api/my/components").json["components"], [])
        self.assertEqual(alice.delete(f"/api/my/components/{comp['id']}", headers=H).status_code, 200)

    def test_auth_required_and_csrf(self):
        c = self.client()
        self.assertEqual(c.get("/api/cart").status_code, 401)
        self.assertEqual(c.post("/api/components", headers=H, json={}).status_code, 401)
        self.assertEqual(c.post("/api/auth/login", json={"email": "a@b.co", "password": "x"}).status_code, 403)

    def test_validation_and_duplicates(self):
        c = self.client()
        r = c.post("/api/auth/register", headers=H, json={"name": "A", "email": "bad", "password": "short"})
        self.assertEqual(r.status_code, 400); self.assertEqual(set(r.json["error"]["fields"]), {"name", "email", "password"})
        self.user("alice")
        r = c.post("/api/auth/register", headers=H, json={"name": "Alice", "email": "ALICE@x.io", "password": "password123"})
        self.assertEqual(r.status_code, 409)
        u = self.user("zed")
        r = u.post("/api/components", headers=H, json={"name": "x", "category": "Nope", "condition": "Good", "quantity": 0})
        self.assertEqual(r.status_code, 400)

    def test_login_rate_limit_and_wrong_password(self):
        self.user("alice"); c = self.client()
        codes = [c.post("/api/auth/login", headers=H, json={"email": "alice@x.io", "password": "wrongwrong"}).status_code for _ in range(6)]
        self.assertEqual(codes[:5], [401] * 5); self.assertEqual(codes[5], 429)

    def test_password_hashed(self):
        self.user("alice")
        c = connect(self.app.config["DATABASE_PATH"])
        h = c.execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertTrue(h.startswith("scrypt:")); self.assertNotIn("password123", h)


class CartAndMisc(Base):
    def approved(self, owner="alice", **kw):
        o = self.user(owner); comp = self.submit(o, **kw)
        self.admin().post(f"/api/admin/components/{comp['id']}/approve", headers=H, json={})
        return o, comp

    def test_cart_rules(self):
        alice, comp = self.approved(quantity=3)
        self.assertEqual(alice.post("/api/cart/items", headers=H, json={"component_id": comp["id"]}).status_code, 400)  # own
        bob = self.user("bob")
        self.assertEqual(bob.post("/api/cart/items", headers=H, json={"component_id": comp["id"], "quantity": 4}).status_code, 409)
        bob.post("/api/cart/items", headers=H, json={"component_id": comp["id"], "quantity": 2})
        self.assertEqual(bob.patch(f"/api/cart/items/{comp['id']}", headers=H, json={"quantity": 3}).json["count"], 3)
        self.assertEqual(bob.patch(f"/api/cart/items/{comp['id']}", headers=H, json={"quantity": 9}).status_code, 409)
        # carts are per-user
        self.assertEqual(self.user("carl").get("/api/cart").json["items"], [])
        # taken down listing disappears from cart
        self.admin().post(f"/api/admin/components/{comp['id']}/reject", headers=H, json={})
        self.assertEqual(bob.get("/api/cart").json["items"], [])
        # unapproved can't be added
        c2 = self.submit(alice)
        self.assertEqual(bob.post("/api/cart/items", headers=H, json={"component_id": c2["id"]}).status_code, 404)

    def test_defective_and_donation_rules(self):
        u = self.user()
        d = self.submit(u, condition="Defective", price=50)
        self.assertEqual((d["route"], d["price"]), ("recycle", 0))
        self.admin().post(f"/api/admin/components/{d['id']}/approve", headers=H, json={})
        self.assertEqual(self.client().get("/api/components").json["components"], [])  # never in marketplace
        g = self.submit(u, route="donate", price=99)
        self.assertEqual(g["price"], 0)

    def test_profile(self):
        u = self.user()
        r = u.put("/api/profile", headers=H, json={"name": "Alice B", "phone": "99", "organization": "WIT"})
        self.assertEqual(r.json["user"]["organization"], "WIT")
        self.assertNotIn("password_hash", r.json["user"])
        self.assertEqual(u.put("/api/profile/password", headers=H, json={"current_password": "bad", "new_password": "newpassword1"}).status_code, 400)
        self.assertEqual(u.put("/api/profile/password", headers=H, json={"current_password": "password123", "new_password": "newpassword1"}).status_code, 200)
        c = self.client()
        self.assertEqual(c.post("/api/auth/login", headers=H, json={"email": "alice@x.io", "password": "newpassword1"}).status_code, 200)

    def test_images(self):
        u = self.user()
        r = u.post("/api/components", headers=H, content_type="multipart/form-data",
                   data={"name": "Pic part", "category": "ICs", "condition": "Good", "quantity": "1", "price": "5",
                         "route": "sell", "images": (io.BytesIO(PNG), "a.png")})
        self.assertEqual(r.status_code, 201, r.json)
        url = r.json["component"]["images"][0]
        self.assertEqual(u.get(url).status_code, 200)                 # owner
        self.assertEqual(self.client().get(url).status_code, 404)     # public: still pending
        self.assertEqual(self.admin().get(url).status_code, 200)      # admin
        bad = u.post("/api/components", headers=H, content_type="multipart/form-data",
                     data={"name": "Bad", "category": "ICs", "condition": "Good", "quantity": "1", "price": "5",
                           "images": (io.BytesIO(b"<script>alert(1)</script>"), "x.png")})
        self.assertEqual(bad.status_code, 400)
        self.admin().post(f"/api/admin/components/{r.json['component']['id']}/approve", headers=H, json={})
        self.assertEqual(self.client().get(url).status_code, 200)     # public after approval

    def test_frontend_and_api_404(self):
        c = self.client()
        self.assertEqual(c.get("/api/nope").json["error"]["code"], "not_found")
        self.assertEqual(c.get("/../app/config.py").status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
