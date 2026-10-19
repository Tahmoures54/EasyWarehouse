# -*- coding: utf-8 -*-
"""مدیریت اتصال SQLite با مدیریت خطای فایل و قفل."""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Iterator, List, Optional, Sequence, Tuple, Union

from app.config import DB_PATH, SCHEMA_PATH


class DatabaseError(Exception):
    """خطای لایه دیتابیس با پیام فارسی."""


class DB:
    """کلاینت سبک SQLite برای یک سیستم دسکتاپ."""

    def __init__(self, path: Optional[Union[str, Path]] = None) -> None:
        self.path = Path(path) if path else Path(DB_PATH)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise DatabaseError(f"عدم دسترسی به پوشه دیتابیس:\n{self.path.parent}\n{exc}") from exc
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(str(self.path), timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            if "locked" in msg:
                raise DatabaseError("فایل دیتابیس قفل است. برنامه دیگری آن را باز کرده است.") from exc
            if "unable to open" in msg or "readonly" in msg:
                raise DatabaseError(f"عدم دسترسی به فایل دیتابیس:\n{self.path}") from exc
            raise DatabaseError(f"خطای دیتابیس: {exc}") from exc

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """اجرای چند عملیات وابسته در یک تراکنش نوشتن اتمیک."""
        conn = self._connect()
        try:
            # قفل نوشتن قبل از خواندن موجودی گرفته می‌شود تا دو خروج هم‌زمان
            # نتوانند هر دو بر اساس یک موجودی قدیمی تأیید شوند.
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise DatabaseError(f"نقض یکتایی یا محدودیت داده: {exc}") from exc
        except sqlite3.OperationalError as exc:
            conn.rollback()
            msg = str(exc).lower()
            if "locked" in msg or "busy" in msg:
                raise DatabaseError("فایل دیتابیس مشغول است؛ چند لحظه بعد دوباره تلاش کنید.") from exc
            raise DatabaseError(f"خطای عملیاتی دیتابیس: {exc}") from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        schema_file = Path(SCHEMA_PATH)
        if not schema_file.exists():
            schema_file = Path(__file__).parent / "schema.sql"
        if not schema_file.exists():
            raise DatabaseError("فایل schema.sql یافت نشد.")
        try:
            with closing(self._connect()) as conn:
                # Upgrade legacy product tables in place. The internal code remains
                # stable for transaction foreign keys; user_code is the editable,
                # non-unique business code. Rebuild only the products table so the
                # old UNIQUE(name) constraint is removed without losing transactions.
                conn.execute("PRAGMA foreign_keys = OFF")
                product_cols = [r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()]
                if product_cols and ("user_code" not in product_cols or "UNIQUE(name)" in (
                    (conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='products'").fetchone() or [""])[0] or ""
                ).replace(" ", "")):
                    conn.execute("BEGIN")
                    conn.execute("""
                        CREATE TABLE products_new (
                            code TEXT PRIMARY KEY,
                            user_code TEXT NOT NULL DEFAULT '',
                            name TEXT NOT NULL,
                            unit TEXT NOT NULL DEFAULT 'عدد',
                            min_stock REAL NOT NULL DEFAULT 0,
                            category TEXT NOT NULL DEFAULT 'عمومی',
                            shelf TEXT NOT NULL DEFAULT ''
                        )
                    """)
                    old_names = set(product_cols)
                    select_user_code = "user_code" if "user_code" in old_names else "code"
                    select_category = "category" if "category" in old_names else "'عمومی'"
                    select_shelf = "shelf" if "shelf" in old_names else "''"
                    conn.execute(f"""
                        INSERT INTO products_new(code, user_code, name, unit, min_stock, category, shelf)
                        SELECT code, COALESCE(NULLIF({select_user_code}, ''), code), name,
                               COALESCE(unit, 'عدد'), COALESCE(min_stock, 0),
                               COALESCE({select_category}, 'عمومی'), COALESCE({select_shelf}, '')
                        FROM products
                    """)
                    conn.execute("DROP TABLE products")
                    conn.execute("ALTER TABLE products_new RENAME TO products")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_name ON products(name)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_cat ON products(category)")
                    conn.commit()
                conn.execute("PRAGMA foreign_keys = ON")
                conn.executescript(schema_file.read_text(encoding="utf-8"))
                cols = [r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()]
                if "category" not in cols:
                    conn.execute("ALTER TABLE products ADD COLUMN category TEXT DEFAULT 'عمومی'")
                if "shelf" not in cols:
                    conn.execute("ALTER TABLE products ADD COLUMN shelf TEXT DEFAULT ''")
                conn.commit()
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError(f"خطا در آماده‌سازی دیتابیس: {exc}") from exc

    def run(self, sql: str, params: Sequence[Any] = ()) -> int:
        try:
            with closing(self._connect()) as conn:
                cur = conn.execute(sql, tuple(params))
                conn.commit()
                return int(cur.lastrowid or cur.rowcount or 0)
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"نقض یکتایی یا محدودیت داده: {exc}") from exc
        except sqlite3.OperationalError as exc:
            raise DatabaseError(f"خطای عملیاتی دیتابیس: {exc}") from exc

    def run_many(self, sql: str, rows: List[Tuple[Any, ...]]) -> int:
        try:
            with closing(self._connect()) as conn:
                cur = conn.executemany(sql, rows)
                conn.commit()
                return int(cur.rowcount or 0)
        except sqlite3.Error as exc:
            raise DatabaseError(f"خطا در درج دسته‌ای: {exc}") from exc

    def one(self, sql: str, params: Sequence[Any] = ()) -> Optional[sqlite3.Row]:
        try:
            with closing(self._connect()) as conn:
                return conn.execute(sql, tuple(params)).fetchone()
        except sqlite3.Error as exc:
            raise DatabaseError(f"خطا در خواندن داده: {exc}") from exc

    def all(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        try:
            with closing(self._connect()) as conn:
                return list(conn.execute(sql, tuple(params)).fetchall())
        except sqlite3.Error as exc:
            raise DatabaseError(f"خطا در خواندن داده: {exc}") from exc
