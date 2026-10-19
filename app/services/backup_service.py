# -*- coding: utf-8 -*-
"""پشتیبان‌گیری و بازیابی دیتابیس."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from app.config import get_db_path


class BackupService:
    """کپی فایل SQLite با مهر تاریخ."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = Path(db_path) if db_path else get_db_path()

    def backup(self, dest_dir: Union[str, Path]) -> Path:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            raise FileNotFoundError("فایل دیتابیس وجود ندارد.")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = dest_dir / f"anbar_backup_{stamp}.db"
        shutil.copy2(self.db_path, target)
        return target

    def restore(self, backup_file: Union[str, Path]) -> Path:
        backup_file = Path(backup_file)
        if not backup_file.exists():
            raise FileNotFoundError("فایل پشتیبان یافت نشد.")
        if backup_file.suffix.lower() not in (".db", ".sqlite", ".sqlite3"):
            raise ValueError("فرمت فایل پشتیبان نامعتبر است.")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            safety = self.db_path.with_suffix(".pre_restore.bak")
            shutil.copy2(self.db_path, safety)
        shutil.copy2(backup_file, self.db_path)
        return self.db_path
