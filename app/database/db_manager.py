# -*- coding: utf-8 -*-
"""مدیریت اتصال SQLite با مدیریت خطای فایل و قفل."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple, Union

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

    def _init_schema(self) -> None:
        schema_file = Path(SCHEMA_PATH)
        if not schema_file.exists():
            schema_file = Path(__file__).parent / "schema.sql"
        if not schema_file.exists():
            raise DatabaseError("فایل schema.sql یافت نشد.")
        try:
            with self._connect() as conn:
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
            with self._connect() as conn:
                cur = conn.execute(sql, tuple(params))
                conn.commit()
                return int(cur.lastrowid or cur.rowcount or 0)
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(f"نقض یکتایی یا محدودیت داده: {exc}") from exc
        except sqlite3.OperationalError as exc:
            raise DatabaseError(f"خطای عملیاتی دیتابیس: {exc}") from exc

    def run_many(self, sql: str, rows: List[Tuple[Any, ...]]) -> int:
        try:
            with self._connect() as conn:
                cur = conn.executemany(sql, rows)
                conn.commit()
                return int(cur.rowcount or 0)
        except sqlite3.Error as exc:
            raise DatabaseError(f"خطا در درج دسته‌ای: {exc}") from exc

    def one(self, sql: str, params: Sequence[Any] = ()) -> Optional[sqlite3.Row]:
        try:
            with self._connect() as conn:
                return conn.execute(sql, tuple(params)).fetchone()
        except sqlite3.Error as exc:
            raise DatabaseError(f"خطا در خواندن داده: {exc}") from exc

    def all(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        try:
            with self._connect() as conn:
                return list(conn.execute(sql, tuple(params)).fetchall())
        except sqlite3.Error as exc:
            raise DatabaseError(f"خطا در خواندن داده: {exc}") from exc
