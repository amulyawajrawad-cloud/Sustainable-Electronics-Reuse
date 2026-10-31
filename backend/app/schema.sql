-- ReCircuit schema (SQLite). Idempotent: safe to run on every start.

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  phone         TEXT,
  organization  TEXT,                       -- college / workshop / company
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admins (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('super_admin', 'reviewer')),
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS components (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  name           TEXT NOT NULL,
  category       TEXT NOT NULL CHECK (category IN ('ICs','Resistors','Boards','Sensors','Transistors','Other')),
  description    TEXT NOT NULL DEFAULT '',
  condition      TEXT NOT NULL CHECK (condition IN ('Excellent','Good','Defective')),
  quantity       INTEGER NOT NULL CHECK (quantity >= 1),
  price          INTEGER NOT NULL CHECK (price >= 0),      -- whole rupees
  original_price INTEGER,                                  -- optional strike-through price
  tag            TEXT,
  emoji          TEXT,
  route          TEXT NOT NULL DEFAULT 'sell' CHECK (route IN ('sell','donate','recycle')),
  status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
  review_note    TEXT,                                     -- admin feedback / rejection reason
  submitted_by   INTEGER REFERENCES users(id)  ON DELETE SET NULL,
  reviewed_by    INTEGER REFERENCES admins(id) ON DELETE SET NULL,
  submitted_at   TEXT NOT NULL,
  reviewed_at    TEXT,
  approved_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_components_status ON components(status);
CREATE INDEX IF NOT EXISTS idx_components_submitter ON components(submitted_by);

CREATE TABLE IF NOT EXISTS component_images (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
  filename     TEXT NOT NULL UNIQUE,
  created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_images_component ON component_images(component_id);

CREATE TABLE IF NOT EXISTS carts (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cart_items (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  cart_id      INTEGER NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
  component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
  quantity     INTEGER NOT NULL CHECK (quantity >= 1),
  UNIQUE (cart_id, component_id)
);

-- "Global Listings": the ONLY thing public endpoints and carts read from.
-- A component is public only if an admin approved it and it is for reuse.
CREATE VIEW IF NOT EXISTS global_listings AS
  SELECT * FROM components
  WHERE status = 'approved' AND route != 'recycle' AND condition != 'Defective';
