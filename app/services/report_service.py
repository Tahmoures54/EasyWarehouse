# -*- coding: utf-8 -*-
"""گزارش‌های موجودی و ردیابی گردش کالا برای انبارداری آسان."""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.config import CATEGORIES
from app.database.db_manager import DB
from app.services.transaction_service import validate_transaction_date

logger = logging.getLogger(__name__)

# --------------------------------------------------------------- constants

STATUS_CRITICAL = "بحرانی"
STATUS_EMPTY = "ناموجود"
STATUS_LOW = "کم‌موجودی"
STATUS_OK = "عادی"

_TYPE_LABELS = {"IN": "ورود", "OUT": "خروج", "RETURN": "عودت"}

_INVENTORY_FIELDS: tuple[str, ...] = (
    "code", "name", "unit", "category", "shelf",
    "min_stock", "stock", "shortage", "status", "last_movement",
)
_TRANSACTION_FIELDS: tuple[str, ...] = (
    "id", "date", "code", "name", "unit", "type", "quantity", "note",
)

# ------------------------------------------------------------------ helpers


def _status_for(stock: float, minimum: float) -> str:
    """تعیین وضعیت؛ با ``Product.is_ok/is_low/is_empty`` هم‌خوان.

    * ``stock < 0``   → بحرانی   (``Product.is_critical``)
    * ``stock == 0``  → ناموجود  (``Product.is_empty``)
    * ``stock < min`` → کم‌موجودی (``Product.is_low``)
    * در غیر این صورت → عادی
    """
    if stock < 0:
        return STATUS_CRITICAL
    if stock == 0:
        return STATUS_EMPTY
    if stock < minimum:
        return STATUS_LOW
    return STATUS_OK


def _sanitize_csv_cell(value: Any) -> Any:
    """جلوگیری از CSV Injection در مقادیر متنی که Excel فرمول تفسیر می‌کند."""
    if not isinstance(value, str) or not value:
        return value
    if value[0] not in ("=", "+", "-", "@", "\t", "\r"):
        return value
    # اعداد منفی «واقعی» نباید escape شوند
    try:
        float(value.replace(",", "."))
        return value
    except ValueError:
        return "'" + value


def _ensure_csv_suffix(target: Path) -> Path:
    return target if target.suffix.lower() == ".csv" else target.with_suffix(".csv")


# ---------------------------------------------------------------- service


class ReportService:
    """ساخت گزارش از داده‌های ثبت‌شده؛ موجودی از تراکنش‌ها محاسبه می‌شود."""

    def __init__(self, db: Optional[DB] = None) -> None:
        self.db = db or DB()

    # ------------------------------------------------------------- inventory

    def inventory_rows(
        self,
        category: Optional[str] = None,
        low_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """وضعیت فعلی موجودی، قفسه، حداقل موجودی و آخرین گردش هر کالا."""
        clauses: List[str] = []
        params: List[object] = []
        if category:
            value = category.strip()
            if value:
                if value not in CATEGORIES:
                    raise ValueError(
                        f"دسته «{value}» معتبر نیست؛ از فهرست مجاز انتخاب کنید."
                    )
                clauses.append("p.category = ?")
                params.append(value)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        rows = self.db.all(
            f"""
            SELECT p.code, p.user_code, p.name, p.unit, p.category, p.shelf,
                   p.min_stock,
                   COALESCE(SUM(CASE
                       WHEN t.type IN ('IN', 'RETURN') THEN t.qty
                       WHEN t.type = 'OUT' THEN -t.qty
                       ELSE 0 END), 0) AS stock,
                   MAX(t.date) AS last_movement
            FROM products p
            LEFT JOIN transactions t ON t.code = p.code
            {where}
            GROUP BY p.code
            ORDER BY p.category, p.name COLLATE NOCASE, p.code
            """,
            tuple(params),
        )

        result: List[Dict[str, Any]] = []
        for row in rows:
            stock = float(row["stock"] or 0)
            minimum = float(row["min_stock"] or 0)
            status = _status_for(stock, minimum)
            if low_only and status == STATUS_OK:
                continue
            result.append({
                "code": row["user_code"] or row["code"],
                "name": row["name"],
                "unit": row["unit"],
                "category": row["category"],
                "shelf": row["shelf"] or "",
                "min_stock": minimum,
                "stock": stock,
                "shortage": round(max(0.0, minimum - stock), 6),
                "status": status,
                "last_movement": row["last_movement"] or "",
            })
        return result


    def stale_inventory_rows(self, days: int = 90, as_of: Optional[str] = None) -> List[Dict[str, Any]]:
        """کالاهای دارای موجودی مثبت که در بازه تعیین‌شده گردش نداشته‌اند."""
        try:
            threshold = int(days)
        except (TypeError, ValueError) as exc:
            raise ValueError("تعداد روز باید عدد صحیح باشد.") from exc
        if threshold < 1 or threshold > 36500:
            raise ValueError("تعداد روز باید بین ۱ و ۳۶۵۰۰ باشد.")
        try:
            reference = date.fromisoformat(as_of) if as_of else date.today()
        except ValueError as exc:
            raise ValueError("تاریخ مبنا باید با قالب YYYY-MM-DD باشد.") from exc
        result = []
        for row in self.inventory_rows():
            stock = float(row["stock"])
            if stock <= 0:
                continue
            last = row["last_movement"]
            if last:
                try:
                    movement_date = date.fromisoformat(last)
                except ValueError:
                    logger.warning("Ignoring invalid last movement date: %r", last)
                    continue
                age = (reference - movement_date).days
                if age < threshold:
                    continue
            else:
                age = None
            result.append({
                **row,
                "days_since_movement": age if age is not None else "بدون گردش",
            })
        return result

    def export_stale_inventory_csv(self, path: str | Path, days: int = 90, as_of: Optional[str] = None) -> Path:
        return self.export_csv(
            path,
            self.stale_inventory_rows(days=days, as_of=as_of),
            fieldnames=_INVENTORY_FIELDS + ("days_since_movement",),
        )

    def inventory_count_template_rows(self) -> List[Dict[str, Any]]:
        """برگه شمارش فیزیکی؛ تهیه فایل به‌تنهایی هیچ موجودی را تغییر نمی‌دهد."""
        return [{
            "code": row["code"], "name": row["name"], "unit": row["unit"],
            "category": row["category"], "shelf": row["shelf"],
            "system_stock": row["stock"], "counted_stock": "",
            "variance": "", "notes": "",
        } for row in self.inventory_rows()]

    def export_inventory_count_template_csv(self, path: str | Path) -> Path:
        return self.export_csv(
            path,
            self.inventory_count_template_rows(),
            fieldnames=("code", "name", "unit", "category", "shelf", "system_stock", "counted_stock", "variance", "notes"),
        )

    # ---------------------------------------------------------- transactions

    def transaction_rows(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        code: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """تاریخچهٔ گردش کالا؛ بازه تاریخ و کد اختیاری است.

        فیلتر ``code`` هم کد داخلی و هم کد تجاری کاربر را می‌پذیرد.
        ``limit`` برای جلوگیری از بارگذاری حجم بزرگ در حافظه است.
        """
        start = validate_transaction_date(start_date) if start_date else None
        end = validate_transaction_date(end_date) if end_date else None
        if start and end and start > end:
            raise ValueError("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")

        clauses: List[str] = []
        params: List[Any] = []
        if start:
            clauses.append("t.date >= ?")
            params.append(start)
        if end:
            clauses.append("t.date <= ?")
            params.append(end)
        if code:
            code_clean = str(code).strip()
            if code_clean:
                clauses.append("(t.code = ? OR p.user_code = ?)")
                params.extend([code_clean, code_clean])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_clause = ""
        if limit is not None:
            try:
                limit_value = int(limit)
            except (TypeError, ValueError) as exc:
                raise ValueError("محدودیت تعداد باید عدد صحیح باشد.") from exc
            if limit_value <= 0:
                raise ValueError("محدودیت تعداد باید بزرگ‌تر از صفر باشد.")
            limit_clause = " LIMIT ?"
            params.append(limit_value)

        rows = self.db.all(
            f"""
            SELECT t.id, t.date, t.code, p.user_code, p.name, p.unit,
                   t.type, t.qty, t.note
            FROM transactions t
            LEFT JOIN products p ON p.code = t.code
            {where}
            ORDER BY t.date DESC, t.id DESC{limit_clause}
            """,
            tuple(params),
        )

        return [{
            "id": int(row["id"]),
            "date": row["date"],
            "code": (row["user_code"] if row["user_code"] else row["code"]),
            "name": row["name"] or "",
            "unit": row["unit"] or "",
            "type": _TYPE_LABELS.get(row["type"], row["type"] or ""),
            "quantity": float(row["qty"]),
            "note": row["note"] or "",
        } for row in rows]

    # --------------------------------------------------------------- kardex

    def kardex_rows(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """کاردکس کامل یک کالا با مانده قبل از بازه و مانده پس از هر گردش."""
        from app.services.transaction_service import STOCK_CASE

        value = str(code or "").strip()
        if not value:
            raise ValueError("کد کالا را برای تهیه کاردکس انتخاب کنید.")
        start = validate_transaction_date(start_date) if start_date else None
        end = validate_transaction_date(end_date) if end_date else None
        if start and end and start > end:
            raise ValueError("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")

        product = self.db.one(
            "SELECT code, user_code, name, unit FROM products "
            "WHERE code = ? OR user_code = ? ORDER BY CASE WHEN code = ? THEN 0 ELSE 1 END LIMIT 1",
            (value, value, value),
        )
        if not product:
            raise ValueError(f"کالایی با کد «{value}» یافت نشد.")
        internal_code = product["code"]

        opening = 0.0
        if start:
            row = self.db.one(
                f"""SELECT COALESCE(SUM({STOCK_CASE}), 0) AS stock
                    FROM transactions t WHERE t.code = ? AND t.date < ?""",
                (internal_code, start),
            )
            opening = float(row["stock"] or 0)

        clauses = ["t.code = ?"]
        params: list[Any] = [internal_code]
        if start:
            clauses.append("t.date >= ?")
            params.append(start)
        if end:
            clauses.append("t.date <= ?")
            params.append(end)

        transactions = self.db.all(
            f"""SELECT t.id, t.date, t.type, t.qty, t.note
                FROM transactions t WHERE {" AND ".join(clauses)}
                ORDER BY t.date ASC, t.id ASC""",
            tuple(params),
        )

        balance = opening
        rows: List[Dict[str, Any]] = []
        for tx in transactions:
            qty = float(tx["qty"])
            tx_type = tx["type"]
            incoming = qty if tx_type in ("IN", "RETURN") else 0.0
            outgoing = qty if tx_type == "OUT" else 0.0
            balance += incoming - outgoing
            rows.append({
                "id": int(tx["id"]),
                "document_no": f"EW-{int(tx['id']):06d}",
                "date": tx["date"],
                "code": product["user_code"] or internal_code,
                "name": product["name"] or "",
                "type": _TYPE_LABELS.get(tx_type, tx_type or ""),
                "incoming": incoming,
                "outgoing": outgoing,
                "balance": balance,
                "unit": product["unit"] or "",
                "note": tx["note"] or "",
            })

        # یک ردیف افتتاحیه باعث می‌شود موجودی ابتدای بازه و تراز قابل فهم باشد.
        if start:
            rows.insert(0, {
                "id": "",
                "document_no": "",
                "date": start,
                "code": product["user_code"] or internal_code,
                "name": product["name"] or "",
                "type": "مانده ابتدای دوره",
                "incoming": 0.0,
                "outgoing": 0.0,
                "balance": opening,
                "unit": product["unit"] or "",
                "note": "مانده محاسبه‌شده از تمام گردش‌های پیش از شروع بازه",
            })
        return rows

    def export_kardex_csv(
        self,
        path: str | Path,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        transaction_type: str = "همه گردش‌ها",
    ) -> Path:
        rows = self.kardex_rows(code, start_date, end_date)
        allowed_types = {"همه گردش‌ها", "ورود", "خروج", "عودت"}
        if transaction_type not in allowed_types:
            raise ValueError("نوع گردش برای خروجی کاردکس معتبر نیست.")
        if transaction_type != "همه گردش‌ها":
            rows = [row for row in rows if row["type"] == "مانده ابتدای دوره" or row["type"] == transaction_type]

        # گزارش کاردکس باید اعداد صحیح را بدون پسوند اعشاری نمایش دهد؛
        # مقدارهای کسری همچنان با دقت اصلی حفظ می‌شوند.
        for row in rows:
            for key in ("incoming", "outgoing", "balance"):
                value = row.get(key)
                if isinstance(value, (int, float)) and float(value).is_integer():
                    row[key] = int(value)

        return self.export_csv(
            path,
            rows,
            fieldnames=("id", "document_no", "date", "code", "name", "type", "incoming", "outgoing", "balance", "unit", "note"),
        )

    # ---------------------------------------------------------------- CSV

    @staticmethod
    def export_csv(
        path: str | Path,
        rows: Sequence[Dict[str, Any]],
        fieldnames: Optional[Sequence[str]] = None,
    ) -> Path:
        """خروجی CSV با BOM برای فارسی؛ مقاوم در برابر تزریق فرمول.

        - اگر ``rows`` خالی و ``fieldnames`` داده نشود، ``ValueError``.
        - اگر ``rows`` خالی و ``fieldnames`` داده شود، فایل با هدر نوشته می‌شود.
        - پسوند فایل به ``.csv`` تصحیح می‌شود.
        """
        target = _ensure_csv_suffix(Path(path))

        if not rows and not fieldnames:
            raise ValueError("برای تهیه گزارش، داده‌ای وجود ندارد.")

        if fieldnames is not None:
            names: List[str] = list(fieldnames)
        else:
            # ردیف اول منبع حقیقت است؛ ترتیب حفظ می‌شود.
            names = list(rows[0].keys())

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=names,
                    extrasaction="ignore",  # کلیدهای اضافی بی‌ضررند، نه بی‌صدا حذف از مخفی
                )
                writer.writeheader()
                for row in rows:
                    writer.writerow(
                        {key: _sanitize_csv_cell(row.get(key, "")) for key in names}
                    )
        except OSError as exc:
            logger.exception("Writing CSV failed: %s", target)
            raise ValueError(f"نوشتن فایل گزارش ناموفق بود: {exc}") from exc
        return target

    # -------------------------------------------------------------- exports

    def export_inventory_csv(
        self,
        path: str | Path,
        category: Optional[str] = None,
        low_only: bool = False,
    ) -> Path:
        return self.export_csv(
            path,
            self.inventory_rows(category=category, low_only=low_only),
            fieldnames=_INVENTORY_FIELDS,
        )

    def export_transactions_csv(
        self,
        path: str | Path,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        code: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Path:
        return self.export_csv(
            path,
            self.transaction_rows(start_date, end_date, code, limit=limit),
            fieldnames=_TRANSACTION_FIELDS,
        )


__all__ = [
    "ReportService",
    "STATUS_CRITICAL",
    "STATUS_EMPTY",
    "STATUS_LOW",
    "STATUS_OK",
]
