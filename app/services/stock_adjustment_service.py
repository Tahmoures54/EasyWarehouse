# -*- coding: utf-8 -*-
"""شمارش و تعدیل کنترل‌شده موجودی با ردیابی و جلوگیری از ثبت تکراری."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from app.database.db_manager import DB

_EPSILON = 1e-9


class StockAdjustmentService:
    """ثبت شمارش فیزیکی به‌صورت سند قابل ردیابی.

    هر ثبت با مرجع یکتا انجام می‌شود، مانده هنگام تأیید دوباره محاسبه
    می‌شود و اگر پس از شروع شمارش تغییر کرده باشد، ثبت رد خواهد شد.
    """

    def __init__(self, db: DB) -> None:
        self.db = db
        with self.db.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_adjustments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference TEXT NOT NULL UNIQUE,
                    product_code TEXT NOT NULL,
                    system_stock REAL NOT NULL,
                    counted_stock REAL NOT NULL CHECK(counted_stock >= 0),
                    variance REAL NOT NULL,
                    reason TEXT NOT NULL,
                    username TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    transaction_id INTEGER,
                    FOREIGN KEY(product_code) REFERENCES products(code) ON DELETE RESTRICT,
                    FOREIGN KEY(transaction_id) REFERENCES transactions(id) ON DELETE RESTRICT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_adjustment_date ON stock_adjustments(created_at DESC)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    username TEXT NOT NULL DEFAULT '',
                    event TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT ''
                )
            """)

    def create(
        self,
        product_code: str,
        counted_stock: float,
        reason: str,
        username: str,
        expected_system_stock: float,
        reference: str,
    ) -> dict[str, Any]:
        code = (product_code or "").strip()
        why = (reason or "").strip()
        actor = (username or "").strip()
        ref = (reference or "").strip()
        if not code:
            raise ValueError("کالا را انتخاب کنید.")
        if not why:
            raise ValueError("علت تعدیل الزامی است.")
        if not actor:
            raise ValueError("کاربر ثبت‌کننده مشخص نیست.")
        if not ref:
            raise ValueError("شناسه ثبت تعدیل نامعتبر است.")
        try:
            counted = float(counted_stock)
            expected = float(expected_system_stock)
        except (TypeError, ValueError) as exc:
            raise ValueError("موجودی شمارش‌شده یا مانده سیستمی نامعتبر است.") from exc
        if not math.isfinite(counted) or counted < 0:
            raise ValueError("موجودی شمارش‌شده باید عددی متناهی و غیرمنفی باشد.")
        if not math.isfinite(expected):
            raise ValueError("مانده سیستمی نامعتبر است.")

        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            if conn.execute("SELECT 1 FROM stock_adjustments WHERE reference=?", (ref,)).fetchone():
                raise ValueError("این شمارش قبلاً ثبت شده است؛ ثبت تکراری مجاز نیست.")
            product = conn.execute("""
                SELECT p.code, p.name, p.unit,
                       COALESCE(SUM(CASE
                           WHEN t.type IN ('IN','RETURN') THEN t.qty
                           WHEN t.type='OUT' THEN -t.qty
                           ELSE 0 END), 0) AS stock
                FROM products p LEFT JOIN transactions t ON t.code=p.code
                WHERE p.code=? GROUP BY p.code
            """, (code,)).fetchone()
            if product is None:
                raise ValueError("کالای انتخاب‌شده دیگر در سیستم وجود ندارد.")
            current = float(product["stock"] or 0)
            if abs(current - expected) > _EPSILON:
                raise ValueError(
                    f"موجودی از زمان شروع شمارش تغییر کرده است (ابتدا: {expected:g}، اکنون: {current:g}). "
                    "فهرست را تازه‌سازی کنید و شمارش را دوباره بررسی کنید."
                )
            variance = counted - current
            tx_id = None
            if abs(variance) > _EPSILON:
                tx_type = "IN" if variance > 0 else "OUT"
                cursor = conn.execute(
                    "INSERT INTO transactions(code, type, qty, date, note) VALUES (?, ?, ?, ?, ?)",
                    (code, tx_type, abs(variance), now[:10], f"تعدیل شمارش {ref} | علت: {why}"),
                )
                tx_id = int(cursor.lastrowid)
            conn.execute("""
                INSERT INTO stock_adjustments
                (reference, product_code, system_stock, counted_stock, variance, reason,
                 username, created_at, transaction_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ref, code, current, counted, variance, why, actor, now, tx_id))
            conn.execute(
                "INSERT INTO audit_log(occurred_at, username, event, details) VALUES (?, ?, ?, ?)",
                (now, actor[:80], "stock_adjustment_created",
                 f"ref={ref}; code={code}; before={current:g}; counted={counted:g}; variance={variance:g}; reason={why}"[:500]),
            )
        return {
            "reference": ref,
            "product_code": code,
            "product_name": product["name"],
            "unit": product["unit"],
            "system_stock": current,
            "counted_stock": counted,
            "variance": variance,
            "transaction_id": tx_id,
            "created_at": now,
        }

    def all(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        return [dict(row) for row in self.db.all("""
            SELECT a.*, p.name AS product_name, p.unit
            FROM stock_adjustments a JOIN products p ON p.code=a.product_code
            ORDER BY a.id DESC LIMIT ?
        """, (limit,))]
