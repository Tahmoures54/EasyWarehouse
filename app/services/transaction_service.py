# -*- coding: utf-8 -*-
"""سرویس تراکنش و محاسبه موجودی."""

from __future__ import annotations

import logging
import math
from datetime import date
from typing import List, Optional, Tuple

from app.config import ALLOW_NEGATIVE_STOCK, TYPES
from app.database.db_manager import DB
from app.models.transaction import Transaction
from app.services.product_service import ProductService

logger = logging.getLogger(__name__)

# --------------------------------------------------------------- constants

# ارقام فارسی/عربی → لاتین (برای ورودی کاربر فارسی‌زبان)
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# CASE مشترک محاسبه موجودی — تنها تعریف، همه‌جا استفاده.
STOCK_CASE = """
    CASE WHEN t.type IN ('IN','RETURN') THEN t.qty
         WHEN t.type = 'OUT' THEN -t.qty
         ELSE 0 END
"""

# ---------------------------------------------------------------- parsing


def parse_positive_qty(raw: str) -> float:
    """اعتبارسنجی مقدار مثبت (عدد صحیح یا اعشاری).

    - ارقام فارسی/عربی به لاتین تبدیل می‌شوند.
    - جداکنندهٔ اعشار ``.`` و ``,`` و ``،`` پذیرفته می‌شود.
    - نماد علمی (``1e5``) و علائم (+/-) پذیرفته **نمی‌شوند**.
    """
    text = (raw or "").strip().translate(_FA_DIGITS)
    text = text.replace("،", ".").replace(",", ".")
    if not text:
        raise ValueError("مقدار را وارد کنید.")
    if text.startswith(("-", "+")):
        raise ValueError("مقدار باید عددی مثبت باشد (بدون علامت).")
    if text.count(".") > 1:
        raise ValueError("فرمت عدد نامعتبر است؛ فقط یک نقطهٔ اعشار مجاز است.")
    allowed = set("0123456789.")
    if any(ch not in allowed for ch in text):
        raise ValueError("مقدار فقط باید عدد باشد (حروف و نمادها مجاز نیست).")
    try:
        qty = float(text)
    except ValueError as exc:
        raise ValueError("مقدار عددی نامعتبر است.") from exc
    if not math.isfinite(qty) or qty <= 0:
        raise ValueError("مقدار باید عددی متناهی و بزرگ‌تر از صفر باشد.")
    return qty


def validate_transaction_date(value: Optional[str]) -> str:
    """تاریخ را فقط با قالب واقعی ISO ``YYYY-MM-DD`` می‌پذیرد.

    - ``None`` → تاریخ امروز (برای «استفاده از پیش‌فرض»).
    - ``""``  → خطای صریح (کاربر به‌اشتباه فیلد را خالی کرده).
    - قالب‌های دیگر (``2026/10/19``، ``20261019``، هفتهٔ ISO) رد می‌شوند
      حتی اگر نسخهٔ Python آن‌ها را بپذیرد، چون مقایسهٔ ``isoformat``
      صورت می‌گیرد.
    """
    if value is None:
        return Transaction.today()
    text = (value or "").strip()
    if not text:
        raise ValueError(
            "تاریخ را وارد کنید؛ قالب صحیح YYYY-MM-DD مانند 2026-10-19 است."
        )
    try:
        parsed = date.fromisoformat(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "تاریخ نامعتبر است؛ قالب صحیح YYYY-MM-DD مانند 2026-10-19 است."
        ) from exc
    if parsed.isoformat() != text:
        raise ValueError(
            "تاریخ نامعتبر است؛ قالب صحیح YYYY-MM-DD مانند 2026-10-19 است."
        )
    return text


# ------------------------------------------------------------------ service


class TransactionService:
    """ثبت ورود / خروج / عودت با سیاست روشن کنترل موجودی.

    قرارداد: هر متد ``add`` یک تراکنش اتمیک است. بررسی موجودی و درج در
    یک ``BEGIN IMMEDIATE`` انجام می‌شوند تا دو خروج هم‌زمان نتوانند بر
    اساس یک موجودی قدیمی هر دو تأیید شوند.
    """

    def __init__(self, db: Optional[DB] = None) -> None:
        self.db = db or DB()
        self.products = ProductService(self.db)

    # -------------------------------------------------------------- add

    def add(
        self,
        code: str,
        type_: str,
        qty: float,
        date_str: Optional[str] = None,
        note: str = "",
        allow_overdraw: Optional[bool] = None,
        party_name: str = "",
        delivered_by: str = "",
        received_by: str = "",
        reference_no: str = "",
    ) -> Tuple[Transaction, Optional[str]]:
        """ثبت یک تراکنش.

        خروجی: ``(تراکنش، هشدار)`` — هشدار ``None`` یعنی وضعیت عادی.
        برای خروجی که موجودی را به صفر یا منفی می‌برد، هشدار داده می‌شود؛
        اگر سیاست ``ALLOW_NEGATIVE_STOCK`` خاموش باشد، منفی‌شدن خطا است.
        """
        type_normalized = (type_ or "").strip().upper()
        if type_normalized not in TYPES:
            raise ValueError("نوع تراکنش باید ورود، خروج یا عودت باشد.")

        try:
            quantity = float(qty)
        except (TypeError, ValueError) as exc:
            raise ValueError("مقدار باید عددی معتبر باشد.") from exc
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("مقدار باید عددی متناهی و بزرگ‌تر از صفر باشد.")

        product_code = (code or "").strip()
        if not product_code:
            raise ValueError("کد کالا را انتخاب کنید.")

        transaction_date = validate_transaction_date(date_str)

        overdraw_allowed = (
            ALLOW_NEGATIVE_STOCK if allow_overdraw is None else allow_overdraw
        )
        if not isinstance(overdraw_allowed, bool):
            raise ValueError("سیاست موجودی منفی باید روشن یا خاموش باشد.")

        note_value = (note or "").strip()
        party_value = (party_name or "").strip()
        delivered_value = (delivered_by or "").strip()
        received_value = (received_by or "").strip()
        reference_value = (reference_no or "").strip()

        warning: Optional[str] = None

        with self.db.transaction() as conn:
            product = conn.execute(
                f"""
                SELECT p.code, p.user_code, p.name, p.unit, p.min_stock,
                       COALESCE(SUM({STOCK_CASE}), 0) AS stock
                FROM products p
                LEFT JOIN transactions t ON p.code = t.code
                WHERE p.code = ?
                GROUP BY p.code
                """,
                (product_code,),
            ).fetchone()
            if not product:
                raise ValueError(f"کالایی با کد {product_code} یافت نشد.")

            stock = float(product["stock"] or 0)
            unit = product["unit"] or "عدد"
            min_stock = float(product["min_stock"] or 0)
            name = product["name"] or ""
            user_code = product["user_code"] or product_code

            if type_normalized == "OUT":
                warning = self._evaluate_outgoing(stock, quantity, min_stock, unit)
                if warning and stock - quantity < 0 and not overdraw_allowed:
                    raise ValueError(warning + "\nثبت خروج انجام نشد.")

            header = conn.execute(
                """INSERT INTO warehouse_documents
                   (document_no, type, date, note, party_name, delivered_by, received_by, reference_no)
                   VALUES ('', ?, ?, ?, ?, ?, ?, ?)""",
                (type_normalized, transaction_date, note_value, party_value,
                 delivered_value, received_value, reference_value),
            )
            document_id = int(header.lastrowid)
            document_no = f"EW-{document_id:06d}"
            conn.execute("UPDATE warehouse_documents SET document_no=? WHERE id=?", (document_no, document_id))
            cursor = conn.execute(
                """INSERT INTO transactions
                   (code, type, qty, date, note, document_no, party_name,
                    delivered_by, received_by, reference_no, document_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (product_code, type_normalized, quantity, transaction_date, note_value,
                 document_no, party_value, delivered_value, received_value, reference_value,
                 document_id),
            )
            new_id = cursor.lastrowid
            if new_id is None:
                raise RuntimeError("شناسهٔ تراکنش جدید از دیتابیس دریافت نشد.")
            if new_id is None:
                raise RuntimeError(
                    "شناسهٔ تراکنش جدید از دیتابیس دریافت نشد."
                )

        if warning:
            logger.info(
                "Transaction accepted with warning | code=%s type=%s qty=%g stock_before=%g stock_after=%g",
                product_code, type_normalized, quantity, stock, stock - quantity,
            )

        transaction = Transaction(
            id=int(new_id),
            code=product_code,
            type=type_normalized,
            qty=quantity,
            date=transaction_date,
            note=note_value,
            name=name,
            unit=unit,
            user_code=user_code,
            document_no=document_no,
            party_name=party_value,
            delivered_by=delivered_value,
            received_by=received_value,
            reference_no=reference_value,
        )
        return transaction, warning

    def add_document(
        self,
        items: list[dict],
        date_str: Optional[str] = None,
        note: str = "",
        party_name: str = "",
        delivered_by: str = "",
        received_by: str = "",
        reference_no: str = "",
        allow_overdraw: Optional[bool] = None,
    ) -> Tuple[list[Transaction], list[str], str]:
        """ثبت اتمیک یک سند با چند قلم؛ در صورت خطا هیچ ردیفی ذخیره نمی‌شود."""
        if not isinstance(items, list) or not items:
            raise ValueError("برای ثبت سند، دست‌کم یک قلم کالا اضافه کنید.")
        tx_date = validate_transaction_date(date_str)
        doc_note = (note or "").strip()
        party = (party_name or "").strip()
        delivered = (delivered_by or "").strip()
        received = (received_by or "").strip()
        reference = (reference_no or "").strip()
        overdraw_allowed = ALLOW_NEGATIVE_STOCK if allow_overdraw is None else allow_overdraw
        if not isinstance(overdraw_allowed, bool):
            raise ValueError("سیاست موجودی منفی باید روشن یا خاموش باشد.")

        normalized = []
        for item in items:
            code = str(item.get("code", "")).strip()
            kind = str(item.get("type", "")).strip().upper()
            if not code:
                raise ValueError("یکی از اقلام سند کد کالا ندارد.")
            if kind not in TYPES:
                raise ValueError("نوع تراکنش باید ورود، خروج یا عودت باشد.")
            try:
                qty = float(item.get("qty"))
            except (TypeError, ValueError) as exc:
                raise ValueError("مقدار یکی از اقلام معتبر نیست.") from exc
            if not math.isfinite(qty) or qty <= 0:
                raise ValueError("مقدار هر قلم باید عددی متناهی و بزرگ‌تر از صفر باشد.")
            normalized.append((code, kind, qty))

        if len({kind for _, kind, _ in normalized}) != 1:
            raise ValueError("در هر سند، نوع همه اقلام باید یکسان باشد.")

        saved: list[Transaction] = []
        warnings: list[str] = []
        with self.db.transaction() as conn:
            header = conn.execute(
                """INSERT INTO warehouse_documents
                   (document_no, type, date, note, party_name, delivered_by, received_by, reference_no)
                   VALUES ('', ?, ?, ?, ?, ?, ?, ?)""",
                (normalized[0][1], tx_date, doc_note, party, delivered, received, reference),
            )
            doc_id = int(header.lastrowid)
            document_no = f"EW-{doc_id:06d}"
            conn.execute(
                "UPDATE warehouse_documents SET document_no = ? WHERE id = ?",
                (document_no, doc_id),
            )
            for code, kind, qty in normalized:
                product = conn.execute(
                    f"""SELECT p.code, p.user_code, p.name, p.unit, p.min_stock,
                        COALESCE(SUM({STOCK_CASE}), 0) AS stock
                        FROM products p LEFT JOIN transactions t ON p.code=t.code
                        WHERE p.code=? GROUP BY p.code""", (code,)
                ).fetchone()
                if not product:
                    raise ValueError(f"کالایی با کد {code} یافت نشد؛ سند ثبت نشد.")
                stock = float(product["stock"] or 0)
                unit = product["unit"] or "عدد"
                min_stock = float(product["min_stock"] or 0)
                if kind == "OUT":
                    warning = self._evaluate_outgoing(stock, qty, min_stock, unit)
                    if warning:
                        if stock - qty < 0 and not overdraw_allowed:
                            raise ValueError(warning + "\nثبت کل سند انجام نشد.")
                        warnings.append(f"{product['name']}: {warning}")
                cur = conn.execute(
                    """INSERT INTO transactions
                       (code, type, qty, date, note, document_no, party_name,
                        delivered_by, received_by, reference_no, document_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (code, kind, qty, tx_date, doc_note, document_no, party,
                     delivered, received, reference, doc_id),
                )
                saved.append(Transaction(
                    id=int(cur.lastrowid), code=code, type=kind, qty=qty, date=tx_date,
                    note=doc_note, name=product["name"] or "", unit=unit,
                    user_code=product["user_code"] or code, document_no=document_no,
                    party_name=party, delivered_by=delivered, received_by=received,
                    reference_no=reference,
                ))
        return saved, warnings, document_no

    @staticmethod
    def _evaluate_outgoing(
        stock: float, qty: float, min_stock: float, unit: str
    ) -> Optional[str]:
        """ارزیابی هشدار برای خروج (بدون نوشتن در دیتابیس)."""
        after = stock - qty

        if after < 0:
            return (
                f"موجودی منفی می‌شود و موجودی کافی نیست. "
                f"موجودی فعلی: {stock:g} {unit}؛ مقدار خروج: {qty:g} {unit}؛ "
                f"کسری: {-after:g} {unit}."
            )
        if after == 0:
            # حتی با min_stock=0 این حالت باید هشدار داشته باشد؛
            # در non-UI گزارش به‌عنوان «ناموجود» دیده می‌شود.
            if min_stock > 0:
                return (
                    f"هشدار: با این خروج، کالا ناموجود می‌شود "
                    f"(کمتر از حداقل {min_stock:g} {unit}). "
                    f"موجودی فعلی: {stock:g} {unit}."
                )
            return (
                f"هشدار: با این خروج، موجودی کالا به صفر می‌رسد. "
                f"موجودی فعلی: {stock:g} {unit}."
            )
        if after < min_stock:
            return (
                f"هشدار: موجودی پس از خروج کمتر از حداقل می‌شود. "
                f"فعلی: {stock:g}؛ حداقل: {min_stock:g}؛ بعد: {after:g}."
            )
        return None

    # ------------------------------------------------------------- delete

    def delete(self, tx_id: int) -> None:
        if isinstance(tx_id, bool) or not isinstance(tx_id, int) or tx_id <= 0:
            raise ValueError("شناسه تراکنش نامعتبر است.")
        deleted = self.db.run("DELETE FROM transactions WHERE id=?", (tx_id,))
        if deleted == 0:
            raise ValueError(f"تراکنشی با شناسه {tx_id} یافت نشد.")

    # --------------------------------------------------------------- read

    def all(self, limit: int = 300) -> List[Transaction]:
        """آخرین ``limit`` تراکنش.

        توجه: این متد **تمام** تراکنش‌ها را برنمی‌گرداند. برای جست‌وجو در
        سابقهٔ کامل، از :meth:`search` با فیلتر تاریخ/کد استفاده کنید —
        فیلتر در UI فقط روی همان ``limit`` ردیف بارگذاری‌شده اعمال می‌شود.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("تعداد تراکنش‌های درخواستی نامعتبر است.")
        rows = self.db.all(
            f"""
            SELECT t.*, p.name, p.unit, p.user_code
            FROM transactions t
            LEFT JOIN products p ON p.code = t.code
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._row_to_transaction(row) for row in rows]

    def search(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        code: Optional[str] = None,
        limit: int = 500,
    ) -> List[Transaction]:
        """جست‌وجوی سابقهٔ تراکنش‌ها با فیلتر تاریخ و کد."""
        start = validate_transaction_date(start_date) if start_date else None
        end = validate_transaction_date(end_date) if end_date else None
        if start and end and start > end:
            raise ValueError("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")

        clauses: list[str] = []
        params: list[object] = []
        if start:
            clauses.append("t.date >= ?")
            params.append(start)
        if end:
            clauses.append("t.date <= ?")
            params.append(end)
        if code:
            value = str(code).strip()
            if value:
                clauses.append("(t.code = ? OR p.user_code = ?)")
                params.extend([value, value])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("تعداد تراکنش‌های درخواستی نامعتبر است.")
        params.append(limit)

        rows = self.db.all(
            f"""
            SELECT t.*, p.name, p.unit, p.user_code
            FROM transactions t
            LEFT JOIN products p ON p.code = t.code
            {where}
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._row_to_transaction(row) for row in rows]

    def get(self, tx_id: int) -> Optional[Transaction]:
        if isinstance(tx_id, bool) or not isinstance(tx_id, int) or tx_id <= 0:
            raise ValueError("شناسه تراکنش نامعتبر است.")
        row = self.db.one(
            """
            SELECT t.*, p.name, p.unit, p.user_code
            FROM transactions t
            LEFT JOIN products p ON p.code = t.code
            WHERE t.id = ?
            """,
            (tx_id,),
        )
        return self._row_to_transaction(row) if row else None

    def document_lines(self, tx_id: int) -> List[Transaction]:
        """همه اقلام سند متعلق به گردش انتخاب‌شده را برمی‌گرداند."""
        tx = self.get(tx_id)
        if tx is None:
            return []
        row = self.db.one("SELECT document_id FROM transactions WHERE id = ?", (tx_id,))
        if row and row["document_id"] is not None:
            rows = self.db.all(
                """SELECT t.*, p.name, p.unit, p.user_code
                   FROM transactions t LEFT JOIN products p ON p.code=t.code
                   WHERE t.document_id = ?
                   ORDER BY t.id""",
                (row["document_id"],),
            )
            return [self._row_to_transaction(item) for item in rows]
        return [tx]

    def count(self) -> int:
        row = self.db.one("SELECT COUNT(*) AS c FROM transactions")
        return int(row["c"]) if row else 0

    @staticmethod
    def _row_to_transaction(row) -> Transaction:
        return Transaction(
            id=int(row["id"]),
            code=row["code"],
            type=row["type"],
            qty=float(row["qty"]),
            date=row["date"],
            note=row["note"] or "",
            name=row["name"] or "",
            unit=row["unit"] or "",
            user_code=(row["user_code"] if "user_code" in row.keys() and row["user_code"]
                       else row["code"]),
            document_no=(row["document_no"] if "document_no" in row.keys() and row["document_no"]
                         else f"EW-{int(row['id']):06d}"),
            party_name=(row["party_name"] if "party_name" in row.keys() else "") or "",
            delivered_by=(row["delivered_by"] if "delivered_by" in row.keys() else "") or "",
            received_by=(row["received_by"] if "received_by" in row.keys() else "") or "",
            reference_no=(row["reference_no"] if "reference_no" in row.keys() else "") or "",
        )

    # --------------------------------------------------------------- stock

    def get_stock(self, code: str) -> Optional[float]:
        """موجودی فعلی کالا یا ``None`` اگر کالا وجود نداشته باشد.

        ``None`` از ``0.0`` متمایز است: کالای موجود با موجودی صفر
        مقدار ``0.0`` برمی‌گرداند.
        """
        product = self.products.get((code or "").strip())
        return product.stock if product else None


__all__ = [
    "STOCK_CASE",
    "TransactionService",
    "parse_positive_qty",
    "validate_transaction_date",
]
