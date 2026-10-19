# -*- coding: utf-8 -*-
"""سرویس کتابخانه کالاها."""

from __future__ import annotations

from typing import List, Optional

from app.config import PRODUCT_CODE_PADDING, PRODUCT_CODE_PREFIX
from app.database.db_manager import DB, DatabaseError
from app.models.product import Product


class ProductService:
    """CRUD کالا با کد خودکار و جلوگیری از نام تکراری."""

    def __init__(self, db: Optional[DB] = None) -> None:
        self.db = db or DB()

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

    def add(
        self,
        name: str,
        unit: str = "عدد",
        min_stock: float = 0.0,
        category: str = "عمومی",
        shelf: str = "",
    ) -> Product:
        """افزودن کالا؛ نام تکراری رد می‌شود."""
        name = (name or "").strip()
        if not name:
            raise ValueError("نام کالا نمی‌تواند خالی باشد.")
        if min_stock < 0:
            raise ValueError("حداقل موجودی نمی‌تواند منفی باشد.")
        existing = self.db.one(
            "SELECT code FROM products WHERE lower(name) = lower(?)",
            (name,),
        )
        if existing:
            raise ValueError(f"کالایی با نام «{name}» قبلاً ثبت شده است.")
        code = self.next_code()
        try:
            self.db.run(
                "INSERT INTO products (code, name, unit, min_stock, category, shelf) VALUES (?,?,?,?,?,?)",
                (code, name, (unit or "عدد").strip(), float(min_stock), category or "عمومی", shelf or ""),
            )
        except DatabaseError as exc:
            raise ValueError(str(exc)) from exc
        return Product(code, name, unit or "عدد", float(min_stock), 0.0, category or "عمومی", shelf or "")

    def update(
        self,
        code: str,
        name: str,
        unit: str,
        min_stock: float,
        category: Optional[str] = None,
        shelf: Optional[str] = None,
    ) -> None:
        """ویرایش کالا."""
        name = (name or "").strip()
        if not name:
            raise ValueError("نام کالا نمی‌تواند خالی باشد.")
        if min_stock < 0:
            raise ValueError("حداقل موجودی نمی‌تواند منفی باشد.")
        dup = self.db.one(
            "SELECT code FROM products WHERE lower(name) = lower(?) AND code <> ?",
            (name, code),
        )
        if dup:
            raise ValueError(f"نام «{name}» برای کالای دیگری استفاده شده است.")
        current = self.get(code)
        if not current:
            raise ValueError(f"کالایی با کد {code} یافت نشد.")
        self.db.run(
            "UPDATE products SET name=?, unit=?, min_stock=?, category=?, shelf=? WHERE code=?",
            (
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
        return [p.label() for p in self.all(category)]

    def code_from_label(self, label: str) -> Optional[str]:
        if not label:
            return None
        return label.split(" - ", 1)[0].strip()

    def count(self) -> int:
        row = self.db.one("SELECT COUNT(*) AS c FROM products")
        return int(row["c"]) if row else 0
