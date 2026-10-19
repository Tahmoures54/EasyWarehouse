-- EasyWarehouse schema v1.0.0

CREATE TABLE IF NOT EXISTS products (
    code      TEXT PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,
    unit      TEXT NOT NULL DEFAULT 'عدد',
    min_stock REAL NOT NULL DEFAULT 0,
    category  TEXT NOT NULL DEFAULT 'عمومی',
    shelf     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS transactions (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    code  TEXT NOT NULL,
    type  TEXT NOT NULL CHECK(type IN ('IN', 'OUT', 'RETURN')),
    qty   REAL NOT NULL CHECK(qty > 0),
    date  TEXT NOT NULL,
    note  TEXT,
    FOREIGN KEY (code) REFERENCES products(code)
);

CREATE INDEX IF NOT EXISTS idx_tx_code ON transactions(code);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_prod_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_prod_cat ON products(category);
