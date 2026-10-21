# -*- coding: utf-8 -*-
"""تبدیل تاریخ میلادی ذخیره‌شده به نمایش و ورودی تاریخ خورشیدی."""

from __future__ import annotations

from datetime import date

import jdatetime

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def today_jalali() -> str:
    """تاریخ امروز به صورت خورشیدی YYYY/MM/DD."""
    return to_jalali(date.today().isoformat())


def to_jalali(value: str) -> str:
    """تبدیل تاریخ میلادی ISO به تاریخ خورشیدی YYYY/MM/DD."""
    try:
        gregorian = date.fromisoformat(str(value).strip())
        jalali = jdatetime.date.fromgregorian(date=gregorian)
        return jalali.strftime("%Y/%m/%d")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"تاریخ میلادی نامعتبر است: {value!r}") from exc


def from_jalali(value: str) -> str:
    """تبدیل ورودی خورشیدی (با ارقام فارسی و جداکننده / یا -) به ISO میلادی."""
    text = (value or "").strip().translate(_FA_DIGITS)
    parts = text.replace("-", "/").split("/")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError("تاریخ را به‌صورت خورشیدی YYYY/MM/DD وارد کنید؛ نمونه: 1405/07/29.")
    try:
        year, month, day = (int(part) for part in parts)
        jalali = jdatetime.date(year, month, day)
        return jalali.togregorian().isoformat()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("تاریخ خورشیدی نامعتبر است؛ سال، ماه و روز را بررسی کنید.") from exc
