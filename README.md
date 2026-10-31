# ReCircuit — Full-Stack Prototype

A community marketplace for reused electronic components. Users submit listings, **admins review them**, and only **approved** items reach the public marketplace.

```
recircuit/
├── frontend/            your original UI (vanilla HTML/CSS/JS) + new pieces
│   ├── recircuit_frontend.html / .css / .js   storefront (edited in place)
│   ├── recircuit_app.css, api.js              new styles + fetch wrapper
│   └── admin.html, admin.js                   new admin dashboard (/admin)
└── backend/             Flask + SQLite REST API (also serves the frontend)
    ├── app/
    │   ├── routes/          HTTP layer: parse request, call service, return JSON
    │   ├── services/        business rules (review workflow, cart rules, uploads)
    │   ├── repositories/    all SQL lives here
    │   ├── schema.sql       database schema (+ `global_listings` view)
    │   ├── security.py      auth, roles/permissions, CSRF guard, rate limit
    │   └── validation.py, serializers.py, errors.py, config.py, db.py
    ├── manage.py            init-db / seed / create-admin / run
    └── tests/test_e2e.py    15 API tests incl. the full Definition-of-Done flow
```

## Quick start

Requires Python 3.10+.

```bash
cd backend
pip install -r requirements.txt

cp .env.example .env          # then edit .env (see below)
python manage.py seed         # creates DB, the first admin, and 8 starter listings
python manage.py run          # http://127.0.0.1:5000
```

* Marketplace: <http://127.0.0.1:5000/>  ·  Admin dashboard: <http://127.0.0.1:5000/admin>
* Admin login = `ADMIN_EMAIL` / `ADMIN_PASSWORD` from your `.env`.
* Run tests: `cd backend && python -m unittest discover -s tests -v`

### Environment variables (`backend/.env`)

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs session cookies. **Set a long random value** (`python -c "import secrets;print(secrets.token_hex(32))"`). If unset, a random one is used and sessions reset on restart. | random |
| `PORT` | Server port | `5000` |
| `DATABASE_PATH` | SQLite file (created automatically) | `data/recircuit.db` |
| `UPLOAD_DIR` | Where listing photos are stored | `uploads` |
| `FRONTEND_DIR` | Folder served as the site | `../frontend` |
| `COOKIE_SECURE` | `true` when served over HTTPS | `false` |
| `ADMIN_NAME/EMAIL/PASSWORD` | First admin, used by `seed` only | — |

### Database commands

```bash
python manage.py init-db                     # create tables (also done automatically on start)
python manage.py seed [--no-demo]            # first admin (+ starter listings unless --no-demo)
python manage.py create-admin --name "Priya" --email priya@x.io --role reviewer   # prompts for password
```
To reset everything, stop the server and delete `backend/data/` and `backend/uploads/`.

## Architecture decisions

* **Flask + SQLite, same origin.** The frontend has no framework/build step, so the backend simply serves it — no CORS, no second server, no paid services. SQLite is a zero-setup file DB; since SQL is isolated in `repositories/`, moving to PostgreSQL later is a contained change.
* **Layering:** routes → services → repositories. Routes never contain SQL; repositories never contain business rules.
* **Publishing is enforced in the database.** `global_listings` is a SQL **view** (`status='approved'` and not a recycling item). Public endpoints, images and carts read *only* from it, so a pending/rejected item can't leak by a forgotten `if`.
* **Two separate logins.** Users and admins are different tables, endpoints and session keys (`user_id` vs `admin_id`; admin sessions expire after 8 h). A user session can never reach `/api/admin/*`; every request re-loads the principal from the DB.
* **Roles:** `reviewer` — review *pending* submissions, view users. `super_admin` — additionally take down/re-open reviewed listings and delete.
* **Security:** scrypt password hashing; HttpOnly + SameSite=Lax cookies; mutating API calls require an `X-Requested-With` header (CSRF defence); login rate limiting; parameterised SQL everywhere; HTML-escaped output; uploads validated by magic bytes, renamed to random names, size/count limited; images of unapproved items are visible only to the owner and admins. Users can only ever act on their own rows (ids come from the session, not the client).

### Behaviour worth knowing
* **Defective items / "Send for recycling"** become recycling requests (price forced to 0). Admins can accept them, but they never appear in the marketplace or cart — matching the original frontend rule.
* **Donations** are forced to ₹0.
* Users can **withdraw** their own pending/rejected submissions; live listings are removed by admins. You can't add **your own** listing to your cart; cart quantity can't exceed stock. Items taken down disappear from carts automatically.
* Checkout is still a demo (no payment/orders), as in the original.
* The marketing stats on the home page are still the original illustrative numbers.

## API reference

Base path `/api`. JSON in/out. Errors: `{"error": {"code", "message", "fields"?}}`.
**All POST/PUT/PATCH/DELETE requests must send header `X-Requested-With: recircuit`** (the bundled `api.js` does this).

### Users
| Method & path | Auth | Description |
|---|---|---|
| `POST /auth/register` | – | `{name,email,password(≥8),phone?,organization?}` → 201, logs in |
| `POST /auth/login` | – | `{email,password}` |
| `POST /auth/logout` | – | |
| `GET /auth/me` | – | `{user}` or `{user:null}` |
| `GET /profile` · `PUT /profile` | user | update `{name,phone,organization}` |
| `PUT /profile/password` | user | `{current_password,new_password}` |

### Components
| Method & path | Auth | Description |
|---|---|---|
| `GET /components?category=&condition=&q=&sort=featured\|low\|high\|newest` | – | **Approved only** |
| `GET /components/<id>` | – | Approved only, else 404 |
| `POST /components` | user | Submit → saved as **pending**. JSON, or `multipart/form-data` with up to 3 `images`. Fields: `name, category(ICs\|Resistors\|Boards\|Sensors\|Transistors\|Other), condition(Excellent\|Good\|Defective), quantity, price, route(sell\|donate\|recycle), description?` |
| `GET /my/components` | user | Own submissions with `status` + `review_note` |
| `DELETE /my/components/<id>` | user (owner) | Withdraw pending/rejected |
| `GET /images/<file>` | – | Public if listed; otherwise owner/admin only |

### Cart (per logged-in user)
| Method & path | Description |
|---|---|
| `GET /cart` | `{items:[{component,quantity}], count, total}` |
| `POST /cart/items` | `{component_id, quantity=1}` (adds) |
| `PATCH /cart/items/<component_id>` | `{quantity}` — `0` removes |
| `DELETE /cart/items/<component_id>` · `DELETE /cart` | remove one / clear |

### Admin (separate session)
| Method & path | Permission | Description |
|---|---|---|
| `POST /admin/auth/login` · `/logout` · `GET /admin/auth/me` | – | |
| `GET /admin/stats` | any admin | `{pending,approved,rejected,total,users}` |
| `GET /admin/components?status=pending\|approved\|rejected&q=&limit=&offset=` | review | All submissions + submitter info |
| `GET /admin/components/<id>` | review | Detail |
| `POST /admin/components/<id>/approve` | review | `{note?}` → published |
| `POST /admin/components/<id>/reject` | review | `{reason?}` → hidden; shown to the user |
| `DELETE /admin/components/<id>` | manage_listings | Permanently delete |
| `GET /admin/users?q=` | view_users | Users + submission counts |

Reviewers may only decide **pending** items; changing an already-reviewed item (take down an approved listing, reconsider a rejected one) needs `manage_listings` (super admin).

## Manual test script (Definition of Done)
1. Open `/`, click **Log in → Sign up**, create user A. Click **List a component**, submit one (optionally with a photo).
2. Refresh: it is **not** in the marketplace; under **👤 → My submissions** it shows *Pending*.
3. Open `/admin`, sign in with the seeded admin → it's in *Pending*. Open it → **Approve** (or **Reject** with a reason).
4. In a private window register user B → the approved item is in the marketplace; click **+** to add it to the cart. A rejected item never shows.
5. Back as user A: *My submissions* shows Approved/Rejected with the admin's feedback.

## Next steps (not in this prototype)
Edit-own-submission, pagination on public listings, email verification/password reset, real orders & payments, Postgres + migrations (Alembic), a shared rate-limit store (Redis), serving behind gunicorn + HTTPS.
