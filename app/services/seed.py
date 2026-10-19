# -*- coding: utf-8 -*-
"""درج کالاهای پرکاربرد در اولین اجرا."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NamedTuple

from app.config import (
    CATEGORIES,
    PRODUCT_CODE_PADDING,
    PRODUCT_CODE_PREFIX,
    UNITS,
)

if TYPE_CHECKING:
    from app.database.db_manager import DB

logger = logging.getLogger(__name__)


class SeedSpec(NamedTuple):
    """مشخصات یک کالای پیش‌فرض برای درج اولیه."""
    name: str
    unit: str = "عدد"
    min_stock: float = 0.0
    category: str = "عمومی"
    shelf: str = ""
    # اگر خالی باشد، کد داخلی (P001…) به‌عنوان کد تجاری استفاده می‌شود.
    user_code: str = ""


# ترتیب: مصرفی‌ها ابتدا (پرکاربردترند) و سپس تکنیکال.
SEED_PRODUCTS: tuple[SeedSpec, ...] = (
    SeedSpec("لیوان کاغذی", "عدد", 50, "مصرفی"),
    SeedSpec("آب معدنی نیم‌لیتری", "شل", 20, "مصرفی"),
    SeedSpec("دستمال رول کوچک", "رول", 20, "مصرفی"),
    SeedSpec("دستمال کاغذی رومیزی", "جعبه", 20, "مصرفی"),
    SeedSpec("خوشبوکننده هوا", "عدد", 10, "مصرفی"),
    SeedSpec("قند ۴۰۰ گرمی", "بسته", 10, "مصرفی"),
    SeedSpec("ژیلت", "عدد", 15, "مصرفی"),
    SeedSpec("مایع دستشویی ۵۰۰", "عدد", 15, "مصرفی"),
    SeedSpec("شامپو سر", "عدد", 10, "مصرفی"),
    SeedSpec("مایع رنگین‌شویی ۳ لیتری", "گالن", 5, "مصرفی"),
    SeedSpec("بالشت", "عدد", 3, "مصرفی"),
    SeedSpec("مایع ظرفشویی ۴ لیتری", "گالن", 3, "مصرفی"),
    SeedSpec("چای کیسه‌ای ۲۵ عددی", "بسته", 10, "مصرفی"),
    SeedSpec("چای ۱۰۰ گرمی", "بسته", 5, "مصرفی"),
    SeedSpec("نوک مداد اتود ۰.۷", "بسته", 5, "مصرفی"),
    SeedSpec("فیلتر آب تصفیه مرحله ۱", "عدد", 2, "تکنیکال"),
    SeedSpec("فیلتر آب تصفیه مرحله ۲", "عدد", 2, "تکنیکال"),
    SeedSpec("فیلتر آب تصفیه مرحله ۳", "عدد", 2, "تکنیکال"),
)


def _validate_specs() -> None:
    """اعتبارسنجی یک‌باره در زمان import.

    اگر روزی کسی یک SeedSpec با واحد/دستهٔ نامعتبر اضافه کند، برنامه
    همان لحظهٔ import با پیام واضح متوقف می‌شود — نه این‌که کاربر بعداً
    با کتابخانهٔ ناقص روبه‌رو شود.
    """
    seen_names: set[str] = set()
    for spec in SEED_PRODUCTS:
        name = spec.name.strip()
        if not name:
            raise RuntimeError(f"نام کالای پیش‌فرض خالی است: {spec!r}")
        if name in seen_names:
            raise RuntimeError(f"نام کالای پیش‌فرض تکراری: {name!r}")
        seen_names.add(name)
        if spec.unit not in UNITS:
            raise RuntimeError(
                f"واحد نامعتبر در کالای پیش‌فرض «{name}»: {spec.unit!r}"
            )
        if spec.category not in CATEGORIES:
            raise RuntimeError(
                f"دسته نامعتبر در کالای پیش‌فرض «{name}»: {spec.category!r}"
            )
        if spec.min_stock < 0:
            raise RuntimeError(
                f"حداقل موجودی منفی در کالای پیش‌فرض «{name}»: {spec.min_stock!r}"
            )


_validate_specs()


def _next_code_number(existing_codes: list[str]) -> int:
    """بزرگ‌ترین شمارهٔ استفاده‌شده + ۱ (برای جلوگیری از استفادهٔ مجدد)."""
    prefix_len = len(PRODUCT_CODE_PREFIX)
    numbers: list[int] = []
    for code in existing_codes:
        if not isinstance(code, str):
            continue
        if not code.startswith(PRODUCT_CODE_PREFIX):
            continue
        suffix = code[prefix_len:]
        if suffix.isdigit():
            numbers.append(int(suffix))
    return max(numbers, default=0) + 1


def seed_if_empty(db: "DB") -> int:
    """اگر جدول کالا خالی باشد، کالاهای پیش‌فرض را در یک تراکنش درج می‌کند.

    ویژگی‌ها:

    * **اتمیک** در سطح بررسی «خالی بودن» + درج: هر دو در یک
      ``BEGIN IMMEDIATE`` انجام می‌شوند تا دو نمونهٔ برنامه نتوانند
      هم‌زمان seed را تکرار کنند.
    * **best-effort در برابر خطای یک ردیف**: اگر یک ردیف به‌دلیل مشکل
      پیش‌بینی‌نشده شکست بخورد، بقیه ادامه می‌یابند و خطا با
      ``logger.exception`` ثبت می‌شود. این عمدی است: تجربهٔ اولین اجرا
      نباید به‌خاطر یک ردیف بد، کاملاً خالی بماند.
    * **کد تجاری خوانا**: در صورت ارائهٔ ``user_code`` در ``SeedSpec``،
      همان ذخیره می‌شود؛ در غیر این صورت کد داخلی (``P001``…) به‌عنوان
      کد تجاری به کار می‌رود (سازگار با رفتار :meth:`ProductService.add`).

    خروجی: تعداد ردیف‌های درج‌شده (۰ اگر جدول از قبل پر بود).
    """
    with db.transaction() as conn:
        (count,) = conn.execute("SELECT COUNT(*) FROM products").fetchone()
        if count > 0:
            return 0

        existing_codes = [row[0] for row in conn.execute("SELECT code FROM products")]
        next_number = _next_code_number(existing_codes)

        inserted = 0
        for spec in SEED_PRODUCTS:
            internal_code = (
                f"{PRODUCT_CODE_PREFIX}"
                f"{next_number:0{PRODUCT_CODE_PADDING}d}"
            )
            next_number += 1
            user_code = spec.user_code.strip() or internal_code
            try:
                conn.execute(
                    "INSERT INTO products "
                    "(code, user_code, name, unit, min_stock, category, shelf) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        internal_code,
                        user_code,
                        spec.name.strip(),
                        spec.unit,
                        float(spec.min_stock),
                        spec.category,
                        spec.shelf or "",
                    ),
                )
                inserted += 1
            except Exception:
                logger.exception(
                    "Seeding product %r failed; continuing with the rest.",
                    spec.name,
                )

    if inserted:
        logger.info("Seeded %d products on first run.", inserted)
    return inserted


__all__ = ["SEED_PRODUCTS", "SeedSpec", "seed_if_empty"]
