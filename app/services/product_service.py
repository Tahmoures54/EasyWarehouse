# -*- coding: utf-8 -*-
"""سرویس کتابخانه کالاها."""

from __future__ import annotations

import logging
import math
from collections import Counter
from contextlib import closing
from typing import Any, Iterable, List, Optional

from app.config import (
    CATEGORIES,
    PRODUCT_CODE_PADDING,
    PRODUCT_CODE_PREFIX,
    UNITS,
)
from app.database.db_manager import DB, DatabaseError
from app.models.product import Product

logger = logging.getLogger(__name__)

# ------------ SQL مشترک: موجودی پویا از روی تراکنش‌ها -------------------------

_STOCK_CASE = """
    CASE WHEN t.type IN ('IN','RETURN') THEN t.qty
         WHEN t.type = 'OUT' THEN -t.qty
         ELSE 0 END
"""

_STOCK_SELECT = f"""
    SELECT p.*, COALESCE(SUM({_STOCK_CASE}), 0) AS stock
    FROM products p
    LEFT JOIN transactions t ON p.code = t.code
"""


def normalize_product_text(value: str) -> str:
    """نرمال‌سازی املا و فاصله برای تشخیص تکراری‌های فارسی."""
    text = (value or "").strip()
    return " ".join(
        text.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک").split()
    ).casefold()


class ProductService:
    """CRUD کالا؛ کد داخلی یکتا است و کد انتخابی کاربر می‌تواند تکراری باشد."""

    def __init__(self, db: Optional[DB] = None) -> None:
        self.db = db or DB()

    @staticmethod
    def normalize_name(value: str) -> str:
        return normalize_product_text(value)

    # ------------------------------------------------------- internal helpers

    @staticmethod
    def _format_code(number: int) -> str:
        return f"{PRODUCT_CODE_PREFIX}{number:0{PRODUCT_CODE_PADDING}d}"

    @staticmethod
    def _extract_numbers(codes: Iterable[str]) -> list[int]:
        prefix_len = len(PRODUCT_CODE_PREFIX)
        numbers: list[int] = []
        for code in codes:
            code = str(code)
            if not code.startswith(PRODUCT_CODE_PREFIX):
                continue
            suffix = code[prefix_len:]
            if suffix.isdigit():
                numbers.append(int(suffix))
        return numbers

    def _next_code_from_conn(self, conn) -> str:
        """محاسبهٔ کد بعدی در همان اتصال (برای استفاده داخل تراکنش)."""
        rows = conn.execute("SELECT code FROM products").fetchall()
        codes = [row[0] for row in rows]
        return self._format_code(max(self._extract_numbers(codes), default=0) + 1)

    def _to_product(self, row: Any) -> Product:
        keys = row.keys() if hasattr(row, "keys") else ()

        def get(key: str, default: Any) -> Any:
            return row[key] if key in keys else default

        user_code = get("user_code", "") or row["code"]
        return Product(
            code=row["code"],
            name=row["name"],
            unit=get("unit", "عدد") or "عدد",
            min_stock=float(get("min_stock", 0) or 0),
            stock=float(get("stock", 0) or 0),
            category=get("category", "عمومی") or "عمومی",
            shelf=get("shelf", "") or "",
            user_code=user_code,
        )

    @staticmethod
    def _validate_min_stock(value: Any) -> float:
        try:
            minimum = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("حداقل موجودی باید عددی معتبر باشد.") from exc
        if not math.isfinite(minimum) or minimum < 0:
            raise ValueError("حداقل موجودی باید عددی متناهی و غیرمنفی باشد.")
        return minimum

    @staticmethod
    def _validate_unit(unit: Optional[str]) -> str:
        value = (unit or "عدد").strip() or "عدد"
        if value not in UNITS:
            raise ValueError(
                f"واحد «{value}» معتبر نیست؛ از فهرست مجاز انتخاب کنید."
            )
        return value

    @staticmethod
    def _validate_category(category: Optional[str]) -> str:
        value = (category or "عمومی").strip() or "عمومی"
        if value not in CATEGORIES:
            raise ValueError(
                f"دسته «{value}» معتبر نیست؛ از فهرست مجاز انتخاب کنید."
            )
        return value

    # ------------------------------------------------------------ public API

    def next_code(self) -> str:
        """تولید کد داخلی بعدی؛ پیش‌نمایش — برای درج واقعی از ``add`` استفاده کنید."""
        with closing(self.db._connect()) as conn:  # noqa: SLF001
            return self._next_code_from_conn(conn)

    def duplicate_warnings(
        self,
        name: str,
        user_code: str,
        exclude_code: Optional[str] = None,
    ) -> List[str]:
        """هشدارهای غیرمسدودکننده دربارهٔ تکرار کد و نام."""
        warnings: List[str] = []
        code = (user_code or "").strip()
        normalized_name = normalize_product_text(name)
        rows = self.db.all("SELECT code, user_code, name FROM products")

        same_code = [
            r for r in rows
            if code
            and (r["user_code"] or "").strip().casefold() == code.casefold()
            and r["code"] != exclude_code
        ]
        same_name = [
            r for r in rows
            if normalized_name
            and normalize_product_text(r["name"]) == normalized_name
            and r["code"] != exclude_code
        ]

        if same_code:
            details = "، ".join(
                f'{r["name"]} (شناسه داخلی {r["code"]})' for r in same_code[:4]
            )
            warnings.append(f"کد «{code}» قبلاً استفاده شده است: {details}.")
        if same_name:
            details = "، ".join(
                f'{r["name"]} (کد {r["user_code"] or r["code"]})'
                for r in same_name[:4]
            )
            warnings.append(f"نام «{name}» قبلاً ثبت شده است: {details}.")
        return warnings

    def add(
        self,
        name: str,
        unit: str = "عدد",
        min_stock: float = 0.0,
        category: str = "عمومی",
        shelf: str = "",
        user_code: str = "",
    ) -> Product:
        """افزودن کالا با کد داخلی خودکار و کد تجاری کاربر.

        کل عملیات (تولید کد داخلی + درج) در یک تراکنش انجام می‌شود تا
        دو فراخوانی هم‌زمان نتوانند یک کد را بگیرند.
        """
        name = (name or "").strip()
        if not name:
            raise ValueError("نام کالا نمی‌تواند خالی باشد.")
        minimum = self._validate_min_stock(min_stock)
        unit_value = self._validate_unit(unit)
        category_value = self._validate_category(category)
        shelf_value = (shelf or "").strip()

        try:
            with self.db.transaction() as conn:
                code = self._next_code_from_conn(conn)
                user_code_value = (user_code or "").strip() or code
                conn.execute(
                    "INSERT INTO products "
                    "(code, user_code, name, unit, min_stock, category, shelf) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        code,
                        user_code_value,
                        name,
                        unit_value,
                        minimum,
                        category_value,
                        shelf_value,
                    ),
                )
        except DatabaseError as exc:
            logger.exception("Product add failed")
            raise ValueError(str(exc)) from exc

        return Product(
            code=code,
            name=name,
            unit=unit_value,
            min_stock=minimum,
            stock=0.0,
            category=category_value,
            shelf=shelf_value,
            user_code=user_code_value,
        )

    def update(
        self,
        code: str,
        name: str,
        unit: str,
        min_stock: float,
        category: Optional[str] = None,
        shelf: Optional[str] = None,
        user_code: Optional[str] = None,
    ) -> None:
        """ویرایش کالا. مقادیر ``None`` یعنی «بدون تغییر»."""
        name = (name or "").strip()
        if not name:
            raise ValueError("نام کالا نمی‌تواند خالی باشد.")
        minimum = self._validate_min_stock(min_stock)
        unit_value = self._validate_unit(unit)

        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT user_code, category, shelf FROM products WHERE code=?",
                (code,),
            ).fetchone()
            if row is None:
                raise ValueError(f"کالایی با کد {code} یافت نشد.")

            current_user_code = (row[0] or "").strip() or code
            new_user_code = (
                current_user_code
                if user_code is None
                else (user_code.strip() or current_user_code)
            )
            new_category = self._validate_category(
                row[1] if category is None else category
            )
            new_shelf = (row[2] if shelf is None else shelf) or ""
            new_shelf = str(new_shelf).strip()

            conn.execute(
                "UPDATE products SET "
                "user_code=?, name=?, unit=?, min_stock=?, category=?, shelf=? "
                "WHERE code=?",
                (
                    new_user_code,
                    name,
                    unit_value,
                    minimum,
                    new_category,
                    new_shelf,
                    code,
                ),
            )

    def delete(self, code: str) -> None:
        """حذف کالا در صورت نبود تراکنش (اتمیک)."""
        try:
            with self.db.transaction() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM transactions WHERE code=?", (code,)
                ).fetchone()
                if row and int(row[0]) > 0:
                    raise ValueError("این کالا تراکنش دارد و قابل حذف نیست.")
                cursor = conn.execute("DELETE FROM products WHERE code=?", (code,))
                if cursor.rowcount == 0:
                    raise ValueError(f"کالایی با کد {code} یافت نشد.")
        except DatabaseError as exc:
            # اگر FK RESTRICT فعال باشد، پیام خام را به پیام کاربرپسند ترجمه کن.
            if "constraint" in str(exc).lower():
                raise ValueError(
                    "این کالا تراکنش دارد و قابل حذف نیست."
                ) from exc
            raise

    def has_transactions(self, code: str) -> bool:
        row = self.db.one(
            "SELECT 1 FROM transactions WHERE code=? LIMIT 1", (code,)
        )
        return row is not None

    # ------------------------------------------------------------- queries

    def get(self, code: str) -> Optional[Product]:
        """یک کالا با موجودی پویا."""
        row = self.db.one(
            f"{_STOCK_SELECT} WHERE p.code = ? GROUP BY p.code",
            (code,),
        )
        return self._to_product(row) if row else None

    def get_by_user_code(self, user_code: str) -> List[Product]:
        """جست‌وجوی سریع بر اساس کد تجاری (بدون محاسبهٔ موجودی)."""
        code = (user_code or "").strip()
        if not code:
            return []
        rows = self.db.all(
            "SELECT * FROM products WHERE lower(user_code) = lower(?)",
            (code,),
        )
        return [self._to_product(r) for r in rows]

    def all(self, category: Optional[str] = None) -> List[Product]:
        """لیست کالاها با موجودی پویا؛ فیلتر دسته اختیاری."""
        if category is not None:
            category = category.strip()
            if category and category not in CATEGORIES:
                # دسته نامعتبر = نتیجه خالی، بدون شکست
                return []
            rows = self.db.all(
                f"{_STOCK_SELECT} WHERE p.category = ? "
                "GROUP BY p.code ORDER BY p.code",
                (category,),
            )
        else:
            rows = self.db.all(
                f"{_STOCK_SELECT} GROUP BY p.code ORDER BY p.code"
            )
        return [self._to_product(r) for r in rows]

    def count(self) -> int:
        row = self.db.one("SELECT COUNT(*) AS c FROM products")
        return int(row["c"]) if row else 0

    # --------------------------------------------------- combobox helpers

    def combo_items(self, category: Optional[str] = None) -> List[str]:
        """لیبل‌های Combobox؛ برای لیبل‌های تکراری، کد داخلی افزوده می‌شود."""
        products = self.all(category)
        if not products:
            return []
        labels = [p.label() for p in products]
        counts = Counter(labels)
        return [
            f"{label} ⟦{product.code}⟧" if counts[label] > 1 else label
            for product, label in zip(products, labels)
        ]

    def code_from_label(self, label: str) -> Optional[str]:
        """استخراج کد داخلی از لیبل Combobox.

        مسیر سریع: اگر مارکر ``⟦code⟧`` حاضر باشد، بدون دیتابیس برمی‌گردد.
        مسیر کند فقط ستون‌های لازم را می‌خواند (نه محاسبهٔ موجودی).
        """
        if not label:
            return None
        marker = " ⟦"
        if marker in label and label.endswith("⟧"):
            return label.rsplit(marker, 1)[1][:-1]

        # مسیر کند: تطبیق دقیق لیبل با ستون‌های حداقلی
        rows = self.db.all("SELECT code, user_code, name FROM products")
        for row in rows:
            user_code = (row["user_code"] or "").strip() or row["code"]
            if f"{user_code} - {row['name']}" == label:
                return row["code"]
        return None


__all__ = ["ProductService", "normalize_product_text"]
