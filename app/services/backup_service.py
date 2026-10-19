# -*- coding: utf-8 -*-
"""پشتیبان‌گیری و بازیابی ایمن دیتابیس SQLite."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from app.config import get_db_path


class BackupService:
    """ساخت بکاپ و بازیابی اتمی پس از بررسی سلامت فایل."""

    VALID_SUFFIXES = {".db", ".sqlite", ".sqlite3"}

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = Path(db_path) if db_path else get_db_path()

    @staticmethod
    def _validate_sqlite(path: Path) -> None:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("فایل پشتیبان خالی یا نامعتبر است.")
        try:
            # mode=ro prevents a validation attempt from modifying the candidate file.
            uri = path.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=5) as conn:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise ValueError("سلامت ساختاری فایل پشتیبان تأیید نشد.")
                tables = {
                    row[0] for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                if not {"products", "transactions"}.issubset(tables):
                    raise ValueError("فایل پشتیبان ساختار دیتابیس انبار را ندارد.")
                product_cols = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
                tx_cols = {row[1] for row in conn.execute("PRAGMA table_info(transactions)")}
                if not {"code", "name", "unit", "min_stock"}.issubset(product_cols):
                    raise ValueError("ساختار جدول کالا در فایل پشتیبان ناسازگار است.")
                if not {"id", "code", "type", "qty", "date"}.issubset(tx_cols):
                    raise ValueError("ساختار جدول تراکنش در فایل پشتیبان ناسازگار است.")
        except ValueError:
            raise
        except (sqlite3.Error, OSError) as exc:
            raise ValueError("فایل پشتیبان خراب است یا دیتابیس SQLite معتبر نیست.") from exc

    def backup(self, dest_dir: Union[str, Path]) -> Path:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        if not self.db_path.is_file():
            raise FileNotFoundError("فایل دیتابیس وجود ندارد.")
        # SQLite backup API includes committed pages safely, unlike copying a live DB file.
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target = dest_dir / f"anbar_backup_{stamp}.db"
        try:
            with sqlite3.connect(str(self.db_path), timeout=10) as source:
                with sqlite3.connect(str(target), timeout=10) as destination:
                    source.backup(destination)
            self._validate_sqlite(target)
            return target
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def restore(self, backup_file: Union[str, Path]) -> Path:
        backup_file = Path(backup_file)
        if not backup_file.is_file():
            raise FileNotFoundError("فایل پشتیبان یافت نشد.")
        if backup_file.suffix.lower() not in self.VALID_SUFFIXES:
            raise ValueError("فرمت فایل پشتیبان نامعتبر است.")
        # Validate before touching the current database.
        self._validate_sqlite(backup_file)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        safety: Optional[Path] = None
        if self.db_path.exists():
            safety = self.db_path.with_name(
                f"{self.db_path.name}.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.bak"
            )
            shutil.copy2(self.db_path, safety)

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.db_path.name}.restore_", suffix=".tmp", dir=str(self.db_path.parent)
        )
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            shutil.copy2(backup_file, temp_path)
            self._validate_sqlite(temp_path)
            os.replace(temp_path, self.db_path)
            return self.db_path
        except Exception:
            temp_path.unlink(missing_ok=True)
            # os.replace is atomic; if it failed, the original DB remains untouched.
            # If a post-replace error is ever raised, restore the safety copy.
            if safety and safety.exists() and not self.db_path.exists():
                shutil.copy2(safety, self.db_path)
            raise
