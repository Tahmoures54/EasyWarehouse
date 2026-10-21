# -*- coding: utf-8 -*-
"""پشتیبان‌گیری و بازیابی ایمن دیتابیس SQLite."""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from app.config import get_db_path

logger = logging.getLogger(__name__)


class BackupService:
    """ساخت بکاپ و بازیابی اتمی پس از بررسی سلامت فایل.

    قرارداد مهم: پیش از فراخوانی ``restore`` هیچ اتصال باز به دیتابیس فعلی
    نباید وجود داشته باشد. کلاس :class:`app.database.db_manager.DB` از اتصال
    کوتاه‌عمر استفاده می‌کند، پس در عمل این شرط برقرار است؛ ولی اگر روزی
    به استخر اتصال مهاجرت کردید، ابتدا استخر را ببندید.

    فایل‌های جانبی ``-wal`` و ``-shm`` در حین restore مدیریت می‌شوند تا
    WAL دیتابیس قدیمی روی دیتابیس جدید replay نشود.
    """

    VALID_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
    SIDECAR_SUFFIXES = ("-wal", "-shm")

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = Path(db_path) if db_path else get_db_path()

    # ------------------------------------------------------------ helpers

    def _sidecar_paths(self) -> tuple[Path, Path]:
        parent = self.db_path.parent
        name = self.db_path.name
        return parent / f"{name}-wal", parent / f"{name}-shm"

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    def _open_sqlite(self, path: Path, *, readonly: bool = False) -> sqlite3.Connection:
        if readonly:
            uri = path.resolve().as_uri() + "?mode=ro"
            return sqlite3.connect(uri, uri=True, timeout=5)
        return sqlite3.connect(str(path), timeout=10)

    def _checkpoint(self) -> None:
        """ادغام WAL در فایل اصلی و خالی‌کردن آن.

        بدون این کار، اگر بلافاصله پس از restore فایل‌های ``-wal`` حذف شوند،
        ممکن است داده‌ای که هنوز در WAL بوده اما commit شده، از دست برود.
        این متد پس از اطمینان از بسته‌بودن همهٔ اتصال‌ها اجرا می‌شود.
        """
        if not self.db_path.is_file():
            return
        try:
            with closing(self._open_sqlite(self.db_path)) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error as exc:
            logger.debug("wal_checkpoint failed: %s", exc, exc_info=True)

    def _remove_sidecars(self) -> None:
        """حذف ``-wal`` و ``-shm``؛ خطاها فقط لاگ می‌شوند.

        فرض بر این است که WAL پیش‌تر checkpoint شده یا کپی ایمنی از داده
        گرفته شده، پس دور ریختن این فایل‌ها ایمن است.
        """
        for sidecar in self._sidecar_paths():
            try:
                sidecar.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Removing sidecar %s failed: %s", sidecar, exc)

    # ---------------------------------------------------------- validation

    def _validate_sqlite(self, path: Path) -> None:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("فایل پشتیبان خالی یا نامعتبر است.")
        try:
            with closing(self._open_sqlite(path, readonly=True)) as conn:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise ValueError("سلامت ساختاری فایل پشتیبان تأیید نشد.")

                # نقض FK در باز کردن بعدی خطا می‌دهد؛ بهتر است زودتر رد شود.
                fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
                if fk_issues:
                    raise ValueError(
                        f"یکپارچگی ارجاعی فایل پشتیبان نقض شده "
                        f"({len(fk_issues)} مورد)."
                    )

                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                if not {"products", "transactions"}.issubset(tables):
                    raise ValueError(
                        "فایل پشتیبان ساختار دیتابیس انبار را ندارد."
                    )

                product_cols = {
                    row[1] for row in conn.execute("PRAGMA table_info(products)")
                }
                tx_cols = {
                    row[1] for row in conn.execute("PRAGMA table_info(transactions)")
                }
                if not {"code", "name", "unit", "min_stock"}.issubset(product_cols):
                    raise ValueError(
                        "ساختار جدول کالا در فایل پشتیبان ناسازگار است."
                    )
                if not {"id", "code", "type", "qty", "date"}.issubset(tx_cols):
                    raise ValueError(
                        "ساختار جدول تراکنش در فایل پشتیبان ناسازگار است."
                    )
        except ValueError:
            raise
        except (sqlite3.Error, OSError) as exc:
            raise ValueError(
                "فایل پشتیبان خراب است یا دیتابیس SQLite معتبر نیست."
            ) from exc

    def verify(self, backup_file: Union[str, Path]) -> None:
        """صرفاً بررسی معتبر بودن فایل پشتیبان بدون بازیابی."""
        path = Path(backup_file)
        if not path.is_file():
            raise FileNotFoundError("فایل پشتیبان یافت نشد.")
        self._validate_sqlite(path)

    # -------------------------------------------------------------- backup

    def backup(self, dest_dir: Union[str, Path]) -> Path:
        """پشتیبان‌گیری ایمن از دیتابیس زنده.

        از SQLite Backup API استفاده می‌شود (نه کپی فایل) تا WAL و
        تراکنش‌های در جریان به‌درستی لحاظ شوند و فایل نتیجه در حالت
        journal پیش‌فرض (DELETE) باشد — بدون فایل جانبی.
        """
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        if not self.db_path.is_file():
            raise FileNotFoundError("فایل دیتابیس وجود ندارد.")

        target = dest_dir / f"{self.db_path.stem}_backup_{self._timestamp()}.db"
        try:
            with closing(self._open_sqlite(self.db_path)) as source:
                with closing(self._open_sqlite(target)) as destination:
                    source.backup(destination)
            self._validate_sqlite(target)
            logger.info("Backup created at %s", target)
            return target
        except sqlite3.OperationalError as exc:
            target.unlink(missing_ok=True)
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                raise RuntimeError(
                    "دیتابیس مشغول است؛ چند لحظه بعد دوباره تلاش کنید."
                ) from exc
            raise
        except Exception:
            target.unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------- restore

    def restore(self, backup_file: Union[str, Path]) -> Path:
        """بازیابی اتمی با مدیریت فایل‌های جانبی WAL.

        مراحل:

        1. اعتبارسنجی فایل ورودی.
        2. ساخت کپی ایمنی از دیتابیس فعلی با SQLite Backup API
           (شامل داده‌های WAL).
        3. checkpoint و حذف فایل‌های ``-wal`` و ``-shm``.
        4. جابه‌جایی دیتابیس قدیمی به کنار، نصب دیتابیس جدید از یک کپی
           تأییدشده، و پاک‌سازی.
        5. اعتبارسنجی دیتابیس نصب‌شده.
        """
        backup_file = Path(backup_file)
        if not backup_file.is_file():
            raise FileNotFoundError("فایل پشتیبان یافت نشد.")
        if backup_file.suffix.lower() not in self.VALID_SUFFIXES:
            raise ValueError("فرمت فایل پشتیبان نامعتبر است.")

        # 1. اعتبارسنجی اولیه فایل ورودی
        self._validate_sqlite(backup_file)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 2. کپی ایمنی از دیتابیس فعلی (با Backup API — شامل WAL)
        safety: Optional[Path] = None
        if self.db_path.exists():
            safety = self._create_safety_backup()
            logger.info("Safety backup saved at %s", safety)

        # 3. آماده‌سازی فایل موقت از دیتابیس جدید
        temp_path, temp_handle_closed = self._stage_backup_copy(backup_file)

        displaced_path: Optional[Path] = None
        try:
            # 4. checkpoint + حذف فایل‌های جانبی WAL قبل از جابه‌جایی
            self._checkpoint()
            if self.db_path.exists():
                displaced_path = self.db_path.with_name(
                    f".{self.db_path.name}.old_{self._timestamp()}"
                )
                os.replace(self.db_path, displaced_path)
            self._remove_sidecars()

            # 5. نصب فایل جدید
            os.replace(temp_path, self.db_path)

            # 6. اعتبارسنجی نهایی
            self._validate_sqlite(self.db_path)

            # 7. پاک‌سازی فایل قدیمی (بی‌خطر — کپی ایمنی هم داریم)
            if displaced_path is not None and displaced_path.exists():
                try:
                    displaced_path.unlink()
                except OSError as exc:
                    logger.warning(
                        "Displaced DB cleanup failed (%s); kept as %s",
                        exc, displaced_path,
                    )

            logger.info("Database restored from %s", backup_file)
            return self.db_path
        except Exception:
            self._handle_restore_failure(temp_path, displaced_path, safety)
            raise

    # ---------------------------------------------------- restore helpers

    def _create_safety_backup(self) -> Path:
        safety = self.db_path.with_name(
            f"{self.db_path.name}.pre_restore_{self._timestamp()}.bak"
        )
        with closing(self._open_sqlite(self.db_path)) as source:
            with closing(self._open_sqlite(safety)) as destination:
                source.backup(destination)
        return safety

    def _stage_backup_copy(self, backup_file: Path) -> tuple[Path, bool]:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.db_path.name}.restore_",
            suffix=".tmp",
            dir=str(self.db_path.parent),
        )
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            shutil.copy2(backup_file, temp_path)
            self._validate_sqlite(temp_path)
            return temp_path, True
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def _handle_restore_failure(
        self,
        temp_path: Path,
        displaced_path: Optional[Path],
        safety: Optional[Path],
    ) -> None:
        temp_path.unlink(missing_ok=True)

        # اگر نصب دیتابیس جدید انجام شده اما اعتبارسنجی نهایی شکست خورده،
        # فایل نصب‌شده را کنار بگذار تا بتوانیم کپی ایمنی را برگردانیم.
        # وجود displaced_path نشان می‌دهد دیتابیس اصلی از مسیر خود جابه‌جا شده بود.
        if self.db_path.exists():
            if displaced_path is None or displaced_path.exists() is False:
                return
            try:
                self.db_path.unlink()
            except OSError as exc:
                logger.exception("Removing failed restored DB failed: %s", exc)
                return
            self._remove_sidecars()

        # ابتدا سراغ safety (کامل) نه displaced (ممکن است WAL نداشته باشد)
        for source, label in (
            (safety, "safety"),
            (displaced_path, "displaced"),
        ):
            if source is None or not source.exists():
                continue
            try:
                shutil.copy2(source, self.db_path)
                logger.warning(
                    "Restore rolled back from %s copy at %s", label, source
                )
                return
            except OSError as exc:
                logger.exception(
                    "Rollback from %s failed (%s): %s", label, source, exc
                )

        logger.error(
            "Restore failed and no usable fallback remained; "
            "manual recovery may be required."
        )
