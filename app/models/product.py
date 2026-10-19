# -*- coding: utf-8 -*-
"""مدل کالا."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar


@dataclass
class Product:
    """نماینده یک کالا در کتابخانه انبار.

    نکات مهم:

    * ``stock`` در دیتابیس ذخیره **نمی‌شود**؛ از جمع گردش‌ها محاسبه می‌شود و
      تنها برای حمل مقدار محاسبه‌شده به لایه‌های نمایش/گزارش در مدل قرار دارد.
    * ``code`` شناسهٔ داخلی پایدار است و کلید خارجی تراکنش‌ها به آن وابسته است.
    * ``user_code`` کد تجاری قابل ویرایش است؛ اگر خالی باشد، ``label()`` به
      ``code`` برمی‌گردد. ``user_code`` یکتا **نیست** — تکرار با تأیید کاربر مجاز است.
    * ``label()`` برای نمایش Combobox است و جداکنندهٔ آن ``" - "`` است؛ مقادیر
      ``code`` و ``name`` نباید شامل این رشته باشند.
    """

    SEPARATOR: ClassVar[str] = " - "

    code: str
    name: str
    unit: str = "عدد"
    min_stock: float = 0.0
    stock: float = 0.0
    category: str = "عمومی"
    shelf: str = ""
    user_code: str = ""

    def __post_init__(self) -> None:
        # نرمال‌سازی مقادیر ممکن است NULL در دیتابیس legacy باشند.
        if self.user_code is None:
            self.user_code = ""
        if self.shelf is None:
            self.shelf = ""
        if self.category is None:
            self.category = "عمومی"
        if self.unit is None:
            self.unit = "عدد"
        if self.stock is None:
            self.stock = 0.0
        if self.min_stock is None:
            self.min_stock = 0.0

    # ---------------------------------------------------------------- نمایش

    def label(self) -> str:
        """فرمت نمایشی بر اساس کد انتخابی کاربر (برای Combobox و لیست)."""
        return f"{self.user_code or self.code}{self.SEPARATOR}{self.name}"

    # ------------------------------------------------------- وضعیت موجودی

    def is_critical(self) -> bool:
        """موجودی منفی — بحرانی‌ترین حالت (فقط اگر ALLOW_NEGATIVE_STOCK فعال باشد)."""
        return self.stock < 0

    def is_empty(self) -> bool:
        """موجودی صفر یا کمتر — کالا عملاً ناموجود است.

        برخلاف ``is_low``، این متد به ``min_stock`` کاری ندارد؛ حتی اگر
        حداقل تعیین نشده باشد (``min_stock=0``)، موجودی صفر «ناموجود» است.
        """
        return self.stock <= 0

    def is_low(self) -> bool:
        """موجودی بین صفر (شامل) و حداقل (غیرشامل).

        توجه: اگر ``min_stock == 0`` باشد، هرگز ``True`` نمی‌شود؛ برای
        «ناموجود» از ``is_empty()`` استفاده کنید.
        """
        return 0 <= self.stock < self.min_stock

    def is_warning(self) -> bool:
        """نیازمند بررسی: کمبود یا بحرانی."""
        return self.is_low() or self.is_critical()

    def is_ok(self) -> bool:
        """موجودی مساعد: بالاتر یا مساوی حداقل و نامنفی.

        پیاده‌سازی صریح (نه ``not is_warning()``) عمدی است تا با ``NaN``
        به‌درستی رفتار کند: ``NaN >= x`` نادرست است پس نتیجه ``False`` می‌شود.
        """
        return self.stock >= self.min_stock and self.stock >= 0

    # ------------------------------------------------------------ سریال‌سازی

    def to_dict(self) -> dict[str, Any]:
        """نمای دیکشنری — برای گزارش‌ها و مقایسه در تست‌ها."""
        return asdict(self)

    @classmethod
    def from_row(cls, row: Any) -> "Product":
        """ساخت از ردیف SQLite با تحمل نبود ستون‌های اختیاری.

        ``row`` می‌تواند ``sqlite3.Row``، ``dict`` یا شیئی با ``keys()`` باشد.
        """
        keys = row.keys() if hasattr(row, "keys") else ()

        def get(key: str, default: Any) -> Any:
            if key in keys:
                value = row[key]
                return default if value is None else value
            return default

        return cls(
            code=row["code"],
            name=row["name"],
            unit=get("unit", "عدد"),
            min_stock=float(get("min_stock", 0.0)),
            stock=float(get("stock", 0.0)),
            category=get("category", "عمومی"),
            shelf=get("shelf", ""),
            user_code=get("user_code", ""),
        )
