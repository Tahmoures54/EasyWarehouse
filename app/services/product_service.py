# -*- coding: utf-8 -*-
"""سرویس کتابخانه کالاها."""

from __future__ import annotations

from typing import List, Optional
import math

from app.config import PRODUCT_CODE_PADDING, PRODUCT_CODE_PREFIX
from app.database.db_manager import DB, DatabaseError
from app.models.product import Product


def normalize_product_text(value: str) -> str:
    """Normalize Persian spelling and whitespace for duplicate warnings."""
    text = (value or "").strip()
    return " ".join(text.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک").split()).casefold()


class ProductService:
    """CRUD کالا؛ کد داخلی یکتا است و کد انتخابی کاربر می‌تواند تکراری باشد."""

    def __init__(self, db: Optional[DB] = None) -> None:
        self.db = db or DB()

    @staticmethod
    def normalize_name(value: str) -> str:
        return normalize_product_text(value)

    def next_code(self) -> str:
        """تولید کد بعدی مثل P001, P002."""
        row = self.db.one("SELECT code FROM products ORDER BY code DESC LIMIT 1")
        if not row:
            return f"{PRODUCT_CODE_PREFIX}{1:0{PRODUCT_CODE_PADDING}d}"
        try:
            num = int(str(row["code"]).replace(PRODUCT_CODE_PREFIX, "")) + 1
        except ValueError:
            num = 1
        return f"{PRODUCT_CODE_PREFIX}{num:0{PRODUCT_CODE_PADDING}d}"

    def duplicate_warnings(self, name: str, user_code: str, exclude_code: Optional[str] = None) -> List[str]:
        """Return non-blocking warnings for duplicate user code and normalized name."""
        warnings: List[str] = []
        code = (user_code or "").strip()
        normalized_name = normalize_product_text(name)
        rows = self.db.all("SELECT code, user_code, name FROM products")
        same_code = [r for r in rows if code and (r["user_code"] or "").strip().casefold() == code.casefold() and r["code"] != exclude_code]
        same_name = [r for r in rows if normalized_name and normalize_product_text(r["name"]) == normalized_name and r["code"] != exclude_code]
        if same_code:
            details = "، ".join(f'{r["name"]} (شناسه داخلی {r["code"]})' for r in same_code[:4])
            warnings.append(f"کد «{code}» قبلاً استفاده شده است: {details}.")
        if same_name:
            details = "، ".join(f'{r["name"]} (کد {r["user_code"]})' for r in same_name[:4])
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
        """Add a product with a user-entered business code."""
        name = (name or "").strip()
        user_code = (user_code or "").strip()
        if not name:
            raise ValueError("نام کالا نمی‌تواند خالی باشد.")
        try:
            min_stock = float(min_stock)
        except (TypeError, ValueError) as exc:
            raise ValueError("حداقل موجودی باید عددی معتبر باشد.") from exc
        if not math.isfinite(min_stock) or min_stock < 0:
            raise ValueError("حداقل موجودی باید عددی متناهی و غیرمنفی باشد.")
        code = self.next_code()
        user_code = user_code or code
        try:
            self.db.run(
                "INSERT INTO products (code, user_code, name, unit, min_stock, category, shelf) VALUES (?,?,?,?,?,?,?)",
                (code, user_code, name, (unit or "عدد").strip(), float(min_stock), category or "عمومی", shelf or ""),
            )
        except DatabaseError as exc:
            raise ValueError(str(exc)) from exc
        return Product(code, name, unit or "عدد", float(min_stock), 0.0, category or "عمومی", shelf or "", user_code)

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
        """ویرایش کالا."""
        name = (name or "").strip()
        if not name:
            raise ValueError("نام کالا نمی‌تواند خالی باشد.")
        try:
            min_stock = float(min_stock)
        except (TypeError, ValueError) as exc:
            raise ValueError("حداقل موجودی باید عددی معتبر باشد.") from exc
        if not math.isfinite(min_stock) or min_stock < 0:
            raise ValueError("حداقل موجودی باید عددی متناهی و غیرمنفی باشد.")
        current = self.get(code)
        if not current:
            raise ValueError(f"کالایی با کد {code} یافت نشد.")
        self.db.run(
            "UPDATE products SET user_code=?, name=?, unit=?, min_stock=?, category=?, shelf=? WHERE code=?",
            (
                (user_code if user_code is not None else current.user_code).strip(),
                name,
                (unit or "عدد").strip(),
                float(min_stock),
                category if category is not None else current.category,
                shelf if shelf is not None else current.shelf,
                code,
            ),
        )

    def delete(self, code: str) -> None:
        """حذف کالا در صورت نبود تراکنش."""
        row = self.db.one("SELECT COUNT(*) AS c FROM transactions WHERE code=?", (code,))
        if row and int(row["c"]) > 0:
            raise ValueError("این کالا تراکنش دارد و قابل حذف نیست.")
        n = self.db.run("DELETE FROM products WHERE code=?", (code,))
        if n == 0:
            raise ValueError(f"کالایی با کد {code} یافت نشد.")

    def _to_product(self, row) -> Product:
        keys = row.keys()
        return Product(
            code=row["code"],
            name=row["name"],
            unit=row["unit"] or "عدد",
            min_stock=float(row["min_stock"] or 0),
            stock=float(row["stock"] or 0),
            category=row["category"] if "category" in keys else "عمومی",
            shelf=row["shelf"] if "shelf" in keys else "",
            user_code=row["user_code"] if "user_code" in keys else row["code"],
        )

    def get(self, code: str) -> Optional[Product]:
        """یک کالا با موجودی پویا."""
        row = self.db.one(
            """
            SELECT p.*, COALESCE(SUM(
                CASE WHEN t.type IN ('IN','RETURN') THEN t.qty
                     WHEN t.type='OUT' THEN -t.qty ELSE 0 END
            ), 0) AS stock
            FROM products p
            LEFT JOIN transactions t ON p.code = t.code
            WHERE p.code = ?
            GROUP BY p.code
            """,
            (code,),
        )
        return self._to_product(row) if row else None

    def all(self, category: Optional[str] = None) -> List[Product]:
        """لیست کالاها با موجودی."""
        if category:
            rows = self.db.all(
                """
                SELECT p.*, COALESCE(SUM(
                    CASE WHEN t.type IN ('IN','RETURN') THEN t.qty
                         WHEN t.type='OUT' THEN -t.qty ELSE 0 END
                ), 0) AS stock
                FROM products p
                LEFT JOIN transactions t ON p.code = t.code
                WHERE p.category = ?
                GROUP BY p.code
                ORDER BY p.code
                """,
                (category,),
            )
        else:
            rows = self.db.all(
                """
                SELECT p.*, COALESCE(SUM(
                    CASE WHEN t.type IN ('IN','RETURN') THEN t.qty
                         WHEN t.type='OUT' THEN -t.qty ELSE 0 END
                ), 0) AS stock
                FROM products p
                LEFT JOIN transactions t ON p.code = t.code
                GROUP BY p.code
                ORDER BY p.code
                """
            )
        return [self._to_product(r) for r in rows]

    def combo_items(self, category: Optional[str] = None) -> List[str]:
        products = self.all(category)
        labels = [p.label() for p in products]
        counts = {label: labels.count(label) for label in labels}
        return [f"{label} ⟦{product.code}⟧" if counts[label] > 1 else label
                for product, label in zip(products, labels)]

    def code_from_label(self, label: str) -> Optional[str]:
        if not label:
            return None
        marker = " ⟦"
        if marker in label and label.endswith("⟧"):
            return label.rsplit(marker, 1)[1][:-1]
        matches = [p for p in self.all() if p.label() == label]
        if len(matches) == 1:
            return matches[0].code
        return None

    def count(self) -> int:
        row = self.db.one("SELECT COUNT(*) AS c FROM products")
        return int(row["c"]) if row else 0
