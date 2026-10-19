# -*- coding: utf-8 -*-
"""مدل کالا."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Product:
    """نماینده یک کالا در کتابخانه انبار."""

    code: str
    name: str
    unit: str = "عدد"
    min_stock: float = 0.0
    stock: float = 0.0
    category: str = "عمومی"
    shelf: str = ""

    def label(self) -> str:
        """فرمت نمایش در Combobox: کد - نام."""
        return f"{self.code} - {self.name}"

    def is_critical(self) -> bool:
        return self.stock < 0

    def is_low(self) -> bool:
        return 0 <= self.stock < self.min_stock

    def is_ok(self) -> bool:
        return self.stock >= self.min_stock
