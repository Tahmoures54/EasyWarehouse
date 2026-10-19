# -*- coding: utf-8 -*-
"""سرویس تراکنش و محاسبه موجودی."""

from __future__ import annotations

import math
from datetime import date
from typing import List, Optional, Tuple

from app.config import ALLOW_NEGATIVE_STOCK
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
    if not math.isfinite(qty) or qty <= 0:
        raise ValueError("مقدار باید عددی متناهی و بزرگ‌تر از صفر باشد.")
    return qty


def validate_transaction_date(value: Optional[str]) -> str:
    """تاریخ را فقط با قالب واقعی ISO YYYY-MM-DD می‌پذیرد."""
    if value is None:
        return Transaction.today()
    text = value.strip()
    if not text:
        raise ValueError("تاریخ را وارد کنید؛ قالب صحیح YYYY-MM-DD مانند 2026-10-19 است.")
    try:
        parsed = date.fromisoformat(text)
    except (TypeError, ValueError) as exc:
        raise ValueError("تاریخ نامعتبر است؛ قالب صحیح YYYY-MM-DD مانند 2026-10-19 است.") from exc
    if parsed.isoformat() != text:
        raise ValueError("تاریخ نامعتبر است؛ قالب صحیح YYYY-MM-DD مانند 2026-10-19 است.")
    return text


class TransactionService:
    """ثبت ورود / خروج / عودت با سیاست روشن کنترل موجودی."""

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
        allow_overdraw: Optional[bool] = None,
    ) -> Tuple[Transaction, Optional[str]]:
        type_ = (type_ or "").upper()
        if type_ not in ("IN", "OUT", "RETURN"):
            raise ValueError("نوع تراکنش باید ورود، خروج یا عودت باشد.")
        try:
            qty = float(qty)
        except (TypeError, ValueError) as exc:
            raise ValueError("مقدار باید عددی معتبر باشد.") from exc
        if not math.isfinite(qty) or qty <= 0:
            raise ValueError("مقدار باید عددی متناهی و بزرگ‌تر از صفر باشد.")
        code = (code or "").strip()
        if not code:
            raise ValueError("کد کالا را انتخاب کنید.")
        date_str = validate_transaction_date(date_str)
        if allow_overdraw is None:
            allow_overdraw = ALLOW_NEGATIVE_STOCK
        if not isinstance(allow_overdraw, bool):
            raise ValueError("سیاست موجودی منفی باید روشن یا خاموش باشد.")

        warning: Optional[str] = None
        clean_note = (note or "").strip() or None

        # بررسی موجودی و درج تراکنش در یک تراکنش اتمیک انجام می‌شوند.
        # BEGIN IMMEDIATE در DB.transaction مانع تأیید خروج‌های هم‌زمان
        # بر اساس یک مقدار موجودی قدیمی می‌شود.
        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT p.code, p.name, p.unit, p.min_stock,
                       COALESCE(SUM(
                           CASE WHEN t.type IN ('IN','RETURN') THEN t.qty
                                WHEN t.type='OUT' THEN -t.qty ELSE 0 END
                       ), 0) AS stock
                FROM products p
                LEFT JOIN transactions t ON p.code = t.code
                WHERE p.code = ?
                GROUP BY p.code
                """,
                (code,),
            ).fetchone()
            if not row:
                raise ValueError(f"کالایی با کد {code} یافت نشد.")

            stock = float(row["stock"] or 0)
            unit = row["unit"] or "عدد"
            min_stock = float(row["min_stock"] or 0)
            if type_ == "OUT":
                after = stock - qty
                if after < 0:
                    warning = (
                        f"موجودی منفی می‌شود و موجودی کافی نیست. موجودی فعلی: {stock:g} {unit}؛ "
                        f"مقدار خروج: {qty:g} {unit}؛ کسری: {-after:g} {unit}."
                    )
                    if not allow_overdraw:
                        raise ValueError(warning + "\nثبت خروج انجام نشد.")
                elif after < min_stock:
                    warning = (
                        f"هشدار: موجودی پس از خروج کمتر از حداقل می‌شود. "
                        f"فعلی: {stock:g}؛ حداقل: {min_stock:g}؛ بعد: {after:g}."
                    )

            cur = conn.execute(
                "INSERT INTO transactions (code, type, qty, date, note) VALUES (?,?,?,?,?)",
                (code, type_, qty, date_str, clean_note),
            )
            tid = int(cur.lastrowid)

        tx = Transaction(
            id=tid, code=code, type=type_, qty=qty, date=date_str,
            note=clean_note or "", name=row["name"], unit=unit,
        )
        return tx, warning

    def delete(self, tx_id: int) -> None:
        if isinstance(tx_id, bool) or not isinstance(tx_id, int) or tx_id <= 0:
            raise ValueError("شناسه تراکنش نامعتبر است.")
        n = self.db.run("DELETE FROM transactions WHERE id=?", (tx_id,))
        if n == 0:
            raise ValueError(f"تراکنشی با شناسه {tx_id} یافت نشد.")

    def all(self, limit: int = 300) -> List[Transaction]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("تعداد تراکنش‌های درخواستی نامعتبر است.")
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
                id=r["id"], code=r["code"], type=r["type"], qty=float(r["qty"]),
                date=r["date"], note=r["note"] or "", name=r["name"], unit=r["unit"],
            )
            for r in rows
        ]

    def get_stock(self, code: str) -> float:
        p = self.products.get((code or "").strip())
        return p.stock if p else 0.0
