-- انبارداری آسان — schema v2.0.0
-- نیازمند PRAGMA foreign_keys = ON (در DB._connect تنظیم می‌شود).
-- این فایل با executescript اجرا می‌شود؛ در SQLite مدرن، اجرا اتمیک است.
-- نسخه از طریق PRAGMA user_version در انتهای فایل تنظیم می‌شود.

-- ============================================================
-- products
-- ============================================================
-- code:      شناسه داخلی پایدار — کلید خارجی تراکنش‌ها به این وابسته است
-- user_code: کد تجاری قابل ویرایش — نه یکتا؛ تکراری بودن با تأیید کاربر مجاز است
-- name:      نام کالا — خالی/فقط‌فاصله مجاز نیست
-- unit:      واحد شمارش (از UNITS در app.config)
-- min_stock: آستانه هشدار کمبود — منفی نیست
-- category:  یکی از CATEGORIES در app.config (CHECK با آن همگام است)
-- shelf:     محل فیزیکی — اختیاری
-- WITHOUT ROWID: PK متنی دارد و تعداد ردیف کم است → صرفه‌جویی فضا و جست‌وجوی سریع‌تر
CREATE TABLE IF NOT EXISTS products (
    code      TEXT PRIMARY KEY,
    user_code TEXT NOT NULL DEFAULT '',
    name      TEXT NOT NULL CHECK (length(trim(name)) > 0),
    unit      TEXT NOT NULL DEFAULT 'عدد',
    min_stock REAL NOT NULL DEFAULT 0 CHECK (min_stock >= 0),
    category  TEXT NOT NULL DEFAULT 'عمومی'
              CHECK (category IN ('مصرفی', 'تکنیکال', 'عمومی')),
    shelf     TEXT NOT NULL DEFAULT ''
) WITHOUT ROWID;

-- ============================================================
-- transactions
-- ============================================================
-- id:   AUTOINCREMENT عمدی است تا شناسه تراکنش حذف‌شده هرگز بازاستفاده نشود
--       (سابقهٔ حسابرسی). هزینه: نگه‌داری جدول sqlite_sequence.
-- code: FK به products.code — ON DELETE RESTRICT جلوی حذف کالای دارای گردش را می‌گیرد
--       ON UPDATE CASCADE اگر روزی code داخلی تغییر کند، گردش‌ها همراهش می‌آیند.
-- qty:  همیشه مثبت (جهت از type استنباط می‌شود)
-- date: YYYY-MM-DD — الگوی GLOB (SQLite regex ندارد ولی GLOB کافی است)
-- note: اختیاری؛ DEFAULT '' برای هم‌خوانی با ستون‌های متنی دیگر
CREATE TABLE IF NOT EXISTS transactions (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    code  TEXT NOT NULL,
    type  TEXT NOT NULL CHECK (type IN ('IN', 'OUT', 'RETURN')),
    qty   REAL NOT NULL CHECK (qty > 0),
    date  TEXT NOT NULL
          CHECK (length(date) = 10
                 AND date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    note  TEXT DEFAULT '',
    FOREIGN KEY (code) REFERENCES products(code)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- ============================================================
-- indexes
-- ============================================================
-- گردش‌ها: فیلتر/گزارش بر اساس کالا، تاریخ، و ترکیب (کالا، تاریخ نزولی)
CREATE INDEX IF NOT EXISTS idx_tx_code      ON transactions(code);
CREATE INDEX IF NOT EXISTS idx_tx_date      ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_tx_code_date ON transactions(code, date DESC);

-- محصولات: جست‌وجوی نام (لیست کالاها)، تشخیص تکراری user_code، فیلتر دسته
CREATE INDEX IF NOT EXISTS idx_prod_name      ON products(name);
CREATE INDEX IF NOT EXISTS idx_prod_user_code ON products(user_code);
-- idx_prod_cat: انتخابی کم‌تمایز (۳ مقدار) — SQLite ممکن است هرگز انتخابش نکند.
-- نگه داشته می‌شود چون هزینه‌اش برای جدول کوچک ناچیز است.
CREATE INDEX IF NOT EXISTS idx_prod_cat ON products(category);

-- ============================================================
-- version
-- ============================================================
-- هم‌راستا با DB.SCHEMA_VERSION در db_manager.py
PRAGMA user_version = 2;
