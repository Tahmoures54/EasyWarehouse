# -*- coding: utf-8 -*-
"""تنظیمات مرکزی EasyWarehouse."""

from __future__ import annotations

import logging
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Final, Mapping

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- metadata

APP_NAME: Final = "EasyWarehouse"
APP_TITLE: Final = "EasyWarehouse - مدیریت انبار"
APP_VERSION: Final = "1.2.0"
APP_AUTHOR: Final = "Tahmoures54"
APP_LICENSE: Final = "MIT"
GITHUB_URL: Final = "https://github.com/Tahmoures54/EasyWarehouse"

APP_GEOMETRY: Final = "1100x700"
APP_MIN_SIZE: Final = (900, 560)

DB_FILENAME: Final = "anbar.db"

# سیاست پیش‌فرض انبار واقعی: خروج بیش از موجودی ممنوع است.
# فقط با تغییر صریح این مقدار به True می‌توان موجودی منفی ثبت کرد.
ALLOW_NEGATIVE_STOCK: Final = False

# ---------------------------------------------------------------- taxonomy

TYPES: Final[Mapping[str, str]] = {
    "IN": "ورود",
    "OUT": "خروج",
    "RETURN": "عودت",
}
TYPE_LABELS: Final[Mapping[str, str]] = {
    "IN": "ورود به انبار",
    "OUT": "خروج از انبار",
    "RETURN": "عودت به انبار",
}

# اگر روزی کسی به یکی از دو دیکشنری بالا کلید اضافه/کم کند، این‌جا فوراً شکست می‌خورد.
if set(TYPES) != set(TYPE_LABELS):
    raise RuntimeError(
        "TYPES و TYPE_LABELS باید کلیدهای یکسانی داشته باشند: "
        f"اختلاف = {set(TYPES) ^ set(TYPE_LABELS)}"
    )

PRODUCT_CODE_PREFIX: Final = "P"
PRODUCT_CODE_PADDING: Final = 3
CATEGORIES: Final[tuple[str, ...]] = ("مصرفی", "تکنیکال", "عمومی")
UNITS: Final[tuple[str, ...]] = (
    "عدد", "جعبه", "بسته", "رول", "کیلو", "گالن", "جفت", "ست", "توپ",
    "پاکت", "لیتر", "متر", "شل",
)


class ConfigError(RuntimeError):
    """خطای پیکربندی که کاربر باید از آن مطلع شود."""


# ------------------------------------------------------------- data folders


def _user_data_dir() -> Path:
    """پوشهٔ دادهٔ اختصاصی برنامه بر اساس پلتفرم."""
    home = Path.home()
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
        return base / APP_NAME
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME

    # Linux / BSD — پیروی از XDG Base Directory Specification
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else home / ".local" / "share"
    return base / APP_NAME


@lru_cache(maxsize=1)
def get_db_path() -> Path:
    """مسیر پایگاه داده؛ پوشهٔ والد در صورت نبود ساخته می‌شود."""
    folder = _user_data_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise ConfigError(
            f"امکان ساخت پوشهٔ داده در «{folder}» وجود ندارد: {exc}"
        ) from exc
    return folder / DB_FILENAME


# ------------------------------------------------------------- resources


def resource_path(*parts: str) -> Path:
    """مسیر منابع؛ در PyInstaller از sys._MEIPASS استفاده می‌شود."""
    meipass = getattr(sys, "_MEIPASS", None)
    base = Path(meipass) if meipass else Path(__file__).resolve().parent.parent
    return base.joinpath(*parts)


SCHEMA_PATH: Final = resource_path("app", "database", "schema.sql")
ICON_PATH: Final = resource_path("assets", "icon.ico")

for _label, _path in (("SCHEMA_PATH", SCHEMA_PATH), ("ICON_PATH", ICON_PATH)):
    if not _path.exists():
        logger.warning("%s not found: %s", _label, _path)


# ------------------------------------------------------------- compatibility


def __getattr__(name: str):
    """دسترسی تنبل به DB_PATH — فقط برای سازگاری با کد قدیمی."""
    if name == "DB_PATH":
        import warnings

        warnings.warn(
            "app.config.DB_PATH دسترسی زودهنگام به دیسک می‌زند؛ "
            "از app.config.get_db_path() استفاده کنید.",
            DeprecationWarning,
            stacklevel=2,
        )
        return get_db_path()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ALLOW_NEGATIVE_STOCK",
    "APP_AUTHOR",
    "APP_GEOMETRY",
    "APP_LICENSE",
    "APP_MIN_SIZE",
    "APP_NAME",
    "APP_TITLE",
    "APP_VERSION",
    "CATEGORIES",
    "ConfigError",
    "DB_FILENAME",
    "DB_PATH",  # منسوخ؛ از get_db_path استفاده کنید
    "GITHUB_URL",
    "ICON_PATH",
    "PRODUCT_CODE_PADDING",
    "PRODUCT_CODE_PREFIX",
    "SCHEMA_PATH",
    "TYPE_LABELS",
    "TYPES",
    "UNITS",
    "get_db_path",
    "resource_path",
]
