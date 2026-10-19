# -*- coding: utf-8 -*-
"""مدل تراکنش."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.config import TYPES


@dataclass
class Transaction:
    """یک رکورد ورود / خروج / عودت."""

    id: Optional[int]
    code: str
    type: str
    qty: float
    date: str
    note: str = ""
    name: str = ""
    unit: str = ""
    user_code: str = ""

    def type_fa(self) -> str:
        return TYPES.get(self.type, self.type)

    @staticmethod
    def today() -> str:
        return date.today().isoformat()
