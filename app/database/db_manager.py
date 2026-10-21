# -*- coding: utf-8 -*-
"""مدیریت اتصال SQLite با مدیریت خطای فایل و قفل."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Iterator, List, Optional, Sequence, Tuple, Union

from app.config import get_db_path, SCHEMA_PATH

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """خطای لایه دیتابیس با پیام فارسی."""


# --------------------------------------------------------------------- helpers

_LOCK_MARKERS = ("locked", "busy")
_OPEN_MARKERS = ("unable to open", "readonly", "read-only")


def _translate_operational(exc: sqlite3.OperationalError, path: Path) -> DatabaseError:
    """تبدیل خطای OperationalError به DatabaseError با پیام فارسی مشخص."""
    message = str(exc).lower()
    if any(marker in message for marker in _LOCK_MARKERS):
        return DatabaseError(
            "فایل دیتابیس مشغول است. برنامه دیگری آن را باز کرده است؛ "
            "چند لحظه بعد دوباره تلاش کنید."
        )
    if any(marker in message for marker in _OPEN_MARKERS):
        return DatabaseError(f"عدم دسترسی به فایل دیتابیس:\n{path}")
    return DatabaseError(f"خطای دیتابیس: {exc}")


# ------------------------------------------------------------------------- DB


class DB:
    """کلاینت سبک SQLite برای یک سیستم دسکتاپ.

    اتصال‌ها کوتاه‌عمر هستند (یک به‌ازای هر عملیات). این انتخاب عمدی است:
    سادگی، ایمنی در برابر استفاده از چند thread، و پرهیز از قفل‌های طولانی.
    برای گزارش‌های سنگین، یک کوئری کافی است (نه حلقه روی رکوردها).
    """

    SCHEMA_VERSION = 3

    def __init__(self, path: Optional[Union[str, Path]] = None) -> None:
        self.path = self._resolve_path(path)
        self._init_schema()

    # ------------------------------------------------------------- lifecycle

    def close(self) -> None:
        """آزادسازی منابع.

        چون هر عملیات اتصال خودش را می‌بندد، این متد امروز no-op است؛
        اما برای سازگاری API (``MainWindow._reload_after_restore``) و
        مهاجرت آینده به استخر اتصال وجود دارد.
        """
        # No-op — see docstring.

    def __enter__(self) -> "DB":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---------------------------------------------------------------- setup

    @staticmethod
    def _resolve_path(path: Optional[Union[str, Path]]) -> Path:
        if path is not None:
            resolved = Path(path)
            try:
                resolved.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise DatabaseError(
                    f"عدم دسترسی به پوشه دیتابیس:\n{resolved.parent}\n{exc}"
                ) from exc
            return resolved

        try:
            return get_db_path()
        except Exception as exc:
            raise DatabaseError(
                f"عدم دسترسی به پوشه دیتابیس:\n{exc}"
            ) from exc

    # -------------------------------------------------------------- connect

    def _connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(
                str(self.path),
                timeout=10.0,
                isolation_level="DEFERRED",
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 10000")
            return conn
        except sqlite3.OperationalError as exc:
            raise _translate_operational(exc, self.path) from exc

    # ---------------------------------------------------------- transaction

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """اجرای چند عملیات وابسته در یک تراکنش نوشتن اتمیک.

        ``BEGIN IMMEDIATE`` قفل RESERVED را فوراً می‌گیرد؛ نویسندگان دیگر
        بلاک می‌شوند و خوانندگان همچنان مجازند. این تضمین می‌کند دو خروج
        هم‌زمان نتوانند بر اساس یک موجودی قدیمی هر دو تأیید شوند.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise DatabaseError(f"نقض یکتایی یا محدودیت داده: {exc}") from exc
        except sqlite3.OperationalError as exc:
            conn.rollback()
            raise _translate_operational(exc, self.path) from exc
        except DatabaseError:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------- schema

    @staticmethod
    def _resolve_schema_file() -> Path:
        candidates = (
            Path(SCHEMA_PATH),
            Path(__file__).resolve().parent / "schema.sql",
        )
        for candidate in candidates:
            try:
                if candidate.is_file() and candidate.stat().st_size > 0:
                    return candidate
            except OSError:
                continue
        raise DatabaseError("فایل schema.sql یافت نشد یا خالی است.")

    def _init_schema(self) -> None:
        schema_file = self._resolve_schema_file()
        try:
            with closing(self._connect()) as conn:
                self._configure_connection(conn)
                self._migrate_products(conn)
                self._apply_schema(conn, schema_file)
                self._ensure_product_columns(conn)
                self._ensure_transaction_document_columns(conn)
                self._stamp_version(conn)
                conn.commit()
        except DatabaseError:
            raise
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"خطا در آماده‌سازی دیتابیس: {exc}") from exc
        except Exception as exc:
            raise DatabaseError(f"خطا در آماده‌سازی دیتابیس: {exc}") from exc

    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        # WAL: خوانندگان و نویسنده هم‌زمان. synchronous=NORMAL با WAL امن است.
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.DatabaseError:
            logger.debug(
                "WAL/synchronous not applied; falling back to defaults",
                exc_info=True,
            )

    def _migrate_products(self, conn: sqlite3.Connection) -> None:
        """ارتقای درجای جدول products از نسخه قدیمی.

        کد داخلی (``code``) پایدار می‌ماند تا FK جدول transactions نشکند؛
        ``user_code`` کد تجاری قابل ویرایش است. فقط جدول products بازسازی
        می‌شود تا قید قدیمی UNIQUE(name) بدون از دست رفتن تراکنش‌ها حذف شود.
        """
        columns = [row[1] for row in conn.execute("PRAGMA table_info(products)")]
        if not columns:
            return  # دیتابیس تازه؛ schema.sql می‌سازد.

        needs_user_code = "user_code" not in columns
        has_unique_name = self._products_has_unique_name(conn, columns)
        if not needs_user_code and not has_unique_name:
            return

        logger.info(
            "Migrating products (missing_user_code=%s, has_unique_name=%s)",
            needs_user_code,
            has_unique_name,
        )

        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                CREATE TABLE products_new (
                    code TEXT PRIMARY KEY,
                    user_code TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL,
                    unit TEXT NOT NULL DEFAULT 'عدد',
                    min_stock REAL NOT NULL DEFAULT 0,
                    category TEXT NOT NULL DEFAULT 'عمومی',
                    shelf TEXT NOT NULL DEFAULT ''
                )
                """
            )
            old = set(columns)
            select_user_code = "user_code" if "user_code" in old else "code"
            select_category = "category" if "category" in old else "'عمومی'"
            select_shelf = "shelf" if "shelf" in old else "''"
            conn.execute(
                f"""
                INSERT INTO products_new
                    (code, user_code, name, unit, min_stock, category, shelf)
                SELECT
                    code,
                    COALESCE(NULLIF({select_user_code}, ''), code),
                    COALESCE(NULLIF(name, ''), code),
                    COALESCE(NULLIF(unit, ''), 'عدد'),
                    COALESCE(min_stock, 0),
                    COALESCE({select_category}, 'عمومی'),
                    COALESCE({select_shelf}, '')
                FROM products
                """
            )
            conn.execute("DROP TABLE products")
            conn.execute("ALTER TABLE products_new RENAME TO products")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_name ON products(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_cat ON products(category)")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            # FK را حتی در صورت خطا برگردان.
            conn.execute("PRAGMA foreign_keys = ON")

    @staticmethod
    def _products_has_unique_name(
        conn: sqlite3.Connection, columns: Sequence[str]
    ) -> bool:
        """تشخیص قید UNIQUE روی name از طریق ایندکس‌های جدول."""
        try:
            indexes = conn.execute("PRAGMA index_list(products)").fetchall()
        except sqlite3.DatabaseError:
            return False
        for index in indexes:
            if index[2] != 1:  # unique flag
                continue
            try:
                cols = conn.execute(
                    f"PRAGMA index_info({index[1]!r})"
                ).fetchall()
            except sqlite3.DatabaseError:
                continue
            names = [c[2].lower() for c in cols]
            if names == ["name"]:
                return True
        return False

    @staticmethod
    def _apply_schema(conn: sqlite3.Connection, schema_file: Path) -> None:
        sql = schema_file.read_text(encoding="utf-8")
        if not sql.strip():
            raise DatabaseError(f"فایل {schema_file} خالی است.")
        try:
            conn.executescript(sql)
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"خطا در اجرای schema: {exc}") from exc

    @staticmethod
    def _ensure_product_columns(conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
        if not columns:
            raise DatabaseError(
                "جدول products پس از اجرای schema.sql ساخته نشد؛ فایل را بررسی کنید."
            )
        migrations = {
            "category": "ALTER TABLE products ADD COLUMN category TEXT DEFAULT 'عمومی'",
            "shelf": "ALTER TABLE products ADD COLUMN shelf TEXT DEFAULT ''",
        }
        for column, statement in migrations.items():
            if column not in columns:
                conn.execute(statement)

    @staticmethod
    def _ensure_transaction_document_columns(conn: sqlite3.Connection) -> None:
        """افزودن فیلدهای سند به گردش‌های قدیمی بدون حذف داده‌ها."""
        columns = {row[1] for row in conn.execute("PRAGMA table_info(transactions)")}
        if not columns:
            raise DatabaseError("جدول transactions پس از اجرای schema.sql ساخته نشد.")
        migrations = {
            "document_no": "ALTER TABLE transactions ADD COLUMN document_no TEXT NOT NULL DEFAULT ''",
            "party_name": "ALTER TABLE transactions ADD COLUMN party_name TEXT NOT NULL DEFAULT ''",
            "delivered_by": "ALTER TABLE transactions ADD COLUMN delivered_by TEXT NOT NULL DEFAULT ''",
            "received_by": "ALTER TABLE transactions ADD COLUMN received_by TEXT NOT NULL DEFAULT ''",
            "reference_no": "ALTER TABLE transactions ADD COLUMN reference_no TEXT NOT NULL DEFAULT ''",
        }
        for column, statement in migrations.items():
            if column not in columns:
                conn.execute(statement)
        conn.execute(
            "UPDATE transactions SET document_no = 'EW-' || printf('%06d', id) "
            "WHERE document_no IS NULL OR trim(document_no) = ''"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_document_no ON transactions(document_no)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tx_party_name ON transactions(party_name)"
        )

    def _stamp_version(self, conn: sqlite3.Connection) -> None:
        current = int(conn.execute("PRAGMA user_version").fetchone()[0] or 0)
        if current < self.SCHEMA_VERSION:
            conn.execute(f"PRAGMA user_version = {int(self.SCHEMA_VERSION)}")

    # ------------------------------------------------------------ write API

    def run(self, sql: str, params: Sequence[Any] = ()) -> int:
        """اجرای یک دستور نوشتن.

        - برای INSERT/REPLACE: ``lastrowid`` (۰ اگر تعریف نشده باشد).
        - برای سایر دستورها: تعداد سطرهای تأثیرگرفته (``rowcount``).

        این تفکیک صریح، ابهام نسخه قبلی را برطرف می‌کند.
        """
        is_insert = sql.lstrip().upper().startswith(("INSERT", "REPLACE"))
        try:
            with closing(self._connect()) as conn:
                cursor = conn.execute(sql, tuple(params))
                conn.commit()
                if is_insert:
                    lastrowid = cursor.lastrowid
                    return int(lastrowid) if lastrowid is not None else 0
                rowcount = cursor.rowcount
                return int(rowcount) if rowcount is not None and rowcount >= 0 else 0
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"نقض یکتایی یا محدودیت داده: {exc}") from exc
        except sqlite3.OperationalError as exc:
            raise _translate_operational(exc, self.path) from exc
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"خطای دیتابیس: {exc}") from exc

    def insert(self, sql: str, params: Sequence[Any] = ()) -> int:
        """نسخهٔ صریح ``run`` برای INSERT — همیشه ``lastrowid`` برمی‌گرداند."""
        try:
            with closing(self._connect()) as conn:
                cursor = conn.execute(sql, tuple(params))
                conn.commit()
                lastrowid = cursor.lastrowid
                return int(lastrowid) if lastrowid is not None else 0
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"نقض یکتایی یا محدودیت داده: {exc}") from exc
        except sqlite3.OperationalError as exc:
            raise _translate_operational(exc, self.path) from exc
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"خطای دیتابیس: {exc}") from exc

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """نسخهٔ صریح ``run`` برای UPDATE/DELETE — همیشه ``rowcount``."""
        try:
            with closing(self._connect()) as conn:
                cursor = conn.execute(sql, tuple(params))
                conn.commit()
                rowcount = cursor.rowcount
                return int(rowcount) if rowcount is not None and rowcount >= 0 else 0
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"نقض یکتایی یا محدودیت داده: {exc}") from exc
        except sqlite3.OperationalError as exc:
            raise _translate_operational(exc, self.path) from exc
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"خطای دیتابیس: {exc}") from exc

    def run_many(self, sql: str, rows: List[Tuple[Any, ...]]) -> int:
        if not rows:
            return 0
        try:
            with closing(self._connect()) as conn:
                cursor = conn.executemany(sql, rows)
                conn.commit()
                rowcount = cursor.rowcount
                return int(rowcount) if rowcount is not None and rowcount >= 0 else 0
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"نقض یکتایی یا محدودیت داده: {exc}") from exc
        except sqlite3.OperationalError as exc:
            raise _translate_operational(exc, self.path) from exc
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"خطا در درج دسته‌ای: {exc}") from exc

    # ------------------------------------------------------------- read API

    def one(self, sql: str, params: Sequence[Any] = ()) -> Optional[sqlite3.Row]:
        try:
            with closing(self._connect()) as conn:
                return conn.execute(sql, tuple(params)).fetchone()
        except sqlite3.OperationalError as exc:
            raise _translate_operational(exc, self.path) from exc
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"خطا در خواندن داده: {exc}") from exc

    def all(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        try:
            with closing(self._connect()) as conn:
                return list(conn.execute(sql, tuple(params)).fetchall())
        except sqlite3.OperationalError as exc:
            raise _translate_operational(exc, self.path) from exc
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"خطا در خواندن داده: {exc}") from exc

    # -------------------------------------------------------- diagnostics

    def integrity_check(self) -> bool:
        """بررسی سلامت فایل دیتابیس (پس از بازیابی مفید است)."""
        try:
            row = self.one("PRAGMA integrity_check")
        except DatabaseError:
            return False
        return row is not None and str(row[0]).lower() == "ok"

    def schema_version(self) -> int:
        """نسخهٔ فعلی schema ذخیره‌شده در فایل دیتابیس."""
        try:
            row = self.one("PRAGMA user_version")
        except DatabaseError:
            return 0
        return int(row[0]) if row is not None else 0
