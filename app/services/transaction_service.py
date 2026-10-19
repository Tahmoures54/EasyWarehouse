# -*- coding: utf-8 -*-
"""سرویس تراکنش و محاسبه موجودی."""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.database.db_manager import DB
from app.models.transaction import Transaction
from app.services.product_service import ProductService


def parse_positive_qty(raw: str) -> float:
    """اعتبارسنجی مقدار مثبت (عدد صحیح یا اعشاری مثبت)."""
    text = (raw or "").strip().replace(",", ".")
    if not text:
        raise ValueError("مقدار را وارد کنید.")
    allowed = set("0123456789.")
    if any(ch not in allowed for ch in text):
        raise ValueError("مقدار فقط باید عدد باشد (حروف مجاز نیست).")
    if text.count(".") > 1:
        raise ValueError("فرمت عدد نامعتبر است.")
    try:
        qty = float(text)
    except ValueError as exc:
        raise ValueError("مقدار عددی نامعتبر است.") from exc
    if qty <= 0:
        raise ValueError("مقدار باید بزرگ‌تر از صفر باشد.")
    return qty


class TransactionService:
    """ثبت ورود / خروج / عودت با هشدار موجودی."""

    def __init__(self, db: Optional[DB] = None) -> None:
        self.db = db or DB()
        self.products = ProductService(self.db)

    def add(
        self,
        code: str,
        type_: str,
        qty: float,
        date_str: Optional[str] = None,
        note: str = "",
        allow_overdraw: bool = True,
    ) -> Tuple[Transaction, Optional[str]]:
        type_ = (type_ or "").upper()
        if type_ not in ("IN", "OUT", "RETURN"):
            raise ValueError("نوع تراکنش باید ورود، خروج یا عودت باشد.")
        qty = float(qty)
        if qty <= 0:
            raise ValueError("مقدار باید بزرگ‌تر از صفر باشد.")

        product = self.products.get(code)
        if not product:
            raise ValueError(f"کالایی با کد {code} یافت نشد.")

        date_str = date_str or Transaction.today()
        warning: Optional[str] = None

        if type_ == "OUT":
            after = product.stock - qty
            if after < 0:
                warning = (
                    f"⚠ موجودی منفی می‌شود!\n"
                    f"موجودی فعلی: {product.stock:g} {product.unit}\n"
                    f"پس از خروج: {after:g} {product.unit}"
                )
                if not allow_overdraw:
                    raise ValueError(warning)
            elif after < product.min_stock:
                warning = (
                    f"⚠ موجودی به زیر حداقل مجاز می‌رسد.\n"
                    f"فعلی: {product.stock:g} | حداقل: {product.min_stock:g} | بعد: {after:g}"
                )

        tid = self.db.run(
            "INSERT INTO transactions (code, type, qty, date, note) VALUES (?,?,?,?,?)",
            (code, type_, qty, date_str, note or None),
        )
        tx = Transaction(
            id=tid,
            code=code,
            type=type_,
            qty=qty,
            date=date_str,
            note=note or "",
            name=product.name,
            unit=product.unit,
        )
        return tx, warning

    def delete(self, tx_id: int) -> None:
        n = self.db.run("DELETE FROM transactions WHERE id=?", (tx_id,))
        if n == 0:
            raise ValueError(f"تراکنشی با شناسه {tx_id} یافت نشد.")

    def all(self, limit: int = 300) -> List[Transaction]:
        rows = self.db.all(
            """
            SELECT t.*, p.name, p.unit
            FROM transactions t
            JOIN products p ON t.code = p.code
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            Transaction(
                id=r["id"],
                code=r["code"],
                type=r["type"],
                qty=float(r["qty"]),
                date=r["date"],
                note=r["note"] or "",
                name=r["name"],
                unit=r["unit"],
            )
            for r in rows
        ]

    def get_stock(self, code: str) -> float:
        p = self.products.get(code)
        return p.stock if p else 0.0
