# -*- coding: utf-8 -*-
"""
تنظیمات مرکزی EasyWarehouse
مسیر دیتابیس در %APPDATA% روی ویندوز قرار می‌گیرد.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "EasyWarehouse"
APP_TITLE = "EasyWarehouse - مدیریت انبار"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Tahmoures54"
APP_LICENSE = "MIT"
GITHUB_URL = "https://github.com/Tahmoures54/EasyWarehouse"
APP_GEOMETRY = "1100x700"
APP_MIN_SIZE = (900, 560)

# انواع تراکنش
TYPES = {"IN": "ورود", "OUT": "خروج", "RETURN": "عودت"}
TYPE_LABELS = {
    "IN": "ورود به انبار",
    "OUT": "خروج از انبار",
    "RETURN": "عودت به انبار",
}

PRODUCT_CODE_PREFIX = "P"
PRODUCT_CODE_PADDING = 3

CATEGORIES = ("مصرفی", "تکنیکال", "عمومی")
UNITS = (
    "عدد", "جعبه", "بسته", "رول", "کیلو", "گالن",
    "جفت", "ست", "توپ", "پاکت", "لیتر", "متر", "شل",
)


def _app_data_dir() -> Path:
    """پوشه داده کاربر (APPDATA روی ویندوز، ~/.local/share روی لینوکس)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def get_db_path() -> Path:
    """مسیر مطلق فایل دیتابیس."""
    folder = _app_data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "anbar.db"


def resource_path(*parts: str) -> Path:
    """
    مسیر منابع (schema، آیکون و ...).
    در حالت PyInstaller از sys._MEIPASS استفاده می‌شود.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent
    return base.joinpath(*parts)


DB_PATH = get_db_path()
SCHEMA_PATH = resource_path("app", "database", "schema.sql")
ICON_PATH = resource_path("assets", "icon.ico")
