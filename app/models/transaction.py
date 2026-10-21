# -*- coding: utf-8 -*-
"""مدل تراکنش."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, ClassVar, Optional

from app.config import TYPE_LABELS, TYPES


@dataclass
class Transaction:
    """یک رکورد ورود / خروج / عودت.

    نکات مهم:

    * ``id = None`` یعنی تراکنش هنوز در دیتابیس ثبت نشده است.
    * ``date`` رشتهٔ ``YYYY-MM-DD`` است (هم‌خوان با ستون TEXT دیتابیس).
      اگر شیء ``date`` یا ``datetime`` داده شود، در ``__post_init__`` به
      ISO-8601 کوتاه تبدیل می‌شود.
    * ``name``، ``unit`` و ``user_code`` از جدول ``products`` با JOIN
      می‌آیند و در جدول ``transactions`` ذخیره **نمی‌شوند**.
    * ``type`` یکی از کلیدهای ``TYPES`` است؛ مقادیر ناشناخته در
      ``type_fa()`` به‌صورت «نامشخص» و در ``signed_qty()`` با ضریب صفر
      برخورد می‌شوند تا مجموع موجودی خراب نشود.
    """

    # جهت اثر روی موجودی: IN/RETURN افزایش، OUT کاهش.
    _TYPE_SIGN: ClassVar[dict[str, int]] = {"IN": +1, "OUT": -1, "RETURN": +1}

    id: Optional[int]
    code: str
    type: str
    qty: float
    date: str
    note: str = ""
    name: str = ""
    unit: str = ""
    user_code: str = ""
    document_no: str = ""
    party_name: str = ""
    delivered_by: str = ""
    received_by: str = ""
    reference_no: str = ""

    # ------------------------------------------------------------ نرمال‌سازی

    def __post_init__(self) -> None:
        # نرمال‌سازی NULLهای legacy به رشتهٔ خالی
        for field in (
            "note", "name", "unit", "user_code", "document_no",
            "party_name", "delivered_by", "received_by", "reference_no",
        ):
            if getattr(self, field) is None:
                setattr(self, field, "")

        # پذیرش date/datetime به‌عنوان میان‌بر
        if isinstance(self.date, datetime):
            self.date = self.date.date().isoformat()
        elif isinstance(self.date, date):
            self.date = self.date.isoformat()

    # --------------------------------------------------------------- نمایش

    def type_fa(self) -> str:
        """برچسب کوتاه فارسی (برای ستون جدول و دیالوگ تأیید).

        در صورت خالی/ناشناخته بودن ``type``، مقدار ایمن «نامشخص» برمی‌گردد
        تا ``None`` یا متن انگلیسی خام به UI راه پیدا نکند.
        """
        if not self.type:
            return "نامشخص"
        return TYPES.get(self.type, f"{self.type} (نامشخص)")

    def type_label_fa(self) -> str:
        """برچسب بلند فارسی (برای پیام موفقیت: «ورود به انبار» و…)."""
        if not self.type:
            return "نامشخص"
        return TYPE_LABELS.get(self.type, self.type_fa())

    # ------------------------------------------------------------ پیش‌بینی

    def is_in(self) -> bool:
        return self.type == "IN"

    def is_out(self) -> bool:
        return self.type == "OUT"

    def is_return(self) -> bool:
        return self.type == "RETURN"

    def signed_qty(self) -> float:
        """مقدار با علامت، برای جمع‌زدن موجودی.

        ``IN`` و ``RETURN`` مثبت، ``OUT`` منفی. اگر ``type`` ناشناخته باشد
        صفر برمی‌گردد تا مجموع موجودی به‌طور بی‌سروصدا خراب نشود؛ خودِ
        ناسازگاری از طریق ``type_fa()`` در UI دیده می‌شود.
        """
        return self._TYPE_SIGN.get(self.type, 0) * self.qty

    def as_date(self) -> date:
        """تاریخ به‌صورت شیء ``date`` برای بازه‌گیری و گزارش."""
        return date.fromisoformat(self.date)

    # ------------------------------------------------------------- کمکی‌ها

    @staticmethod
    def today() -> str:
        """تاریخ محلی امروز به فرمت ``YYYY-MM-DD``."""
        return date.today().isoformat()

    def validate(self) -> None:
        """اعتبارسنجی صریح؛ در صورت خطا ``ValueError`` با پیام فارسی.

        این متد به‌صورت خودکار در سازنده فراخوانی **نمی‌شود** تا بتوان
        تراکنش نیمه‌ساخته (مثلاً برای تست یا پیش‌نمایش) نگه داشت. سرویس
        ثبت باید آن را قبل از ``INSERT`` صدا بزند.
        """
        if not (self.code or "").strip():
            raise ValueError("کد کالا نمی‌تواند خالی باشد.")
        if self.type not in TYPES:
            raise ValueError(f"نوع تراکنش نامعتبر است: {self.type!r}")
        if self.qty is None or self.qty <= 0:
            raise ValueError("مقدار تراکنش باید مثبت باشد.")
        try:
            date.fromisoformat(self.date)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"تاریخ باید YYYY-MM-DD باشد، دریافت شد: {self.date!r}"
            ) from exc

    # ---------------------------------------------------------- سریال‌سازی

    def to_dict(self) -> dict[str, Any]:
        """نمای دیکشنری — برای گزارش‌ها و مقایسه در تست‌ها."""
        return asdict(self)

    @classmethod
    def from_row(cls, row: Any) -> "Transaction":
        """ساخت از ردیف SQLite با تحمل نبود ستون‌های الحاقی.

        ستون‌های ``name``، ``unit`` و ``user_code`` اختیاری‌اند (از JOIN
        می‌آیند). ``row`` می‌تواند ``sqlite3.Row``، ``dict`` یا هر شیئی
        با ``keys()`` باشد.
        """
        keys = row.keys() if hasattr(row, "keys") else ()

        def get(key: str, default: Any) -> Any:
            if key in keys:
                value = row[key]
                return default if value is None else value
            return default

        return cls(
            id=row["id"],
            code=row["code"],
            type=row["type"],
            qty=float(row["qty"]),
            date=row["date"],
            note=get("note", ""),
            name=get("name", ""),
            unit=get("unit", ""),
            user_code=get("user_code", ""),
            document_no=get("document_no", ""),
            party_name=get("party_name", ""),
            delivered_by=get("delivered_by", ""),
            received_by=get("received_by", ""),
            reference_no=get("reference_no", ""),
        )
