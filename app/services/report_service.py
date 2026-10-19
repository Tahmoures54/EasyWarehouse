# -*- coding: utf-8 -*-
"""گزارش‌های موجودی و ردیابی گردش کالا برای EasyWarehouse."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

from app.database.db_manager import DB
from app.services.transaction_service import validate_transaction_date


class ReportService:
    """ساخت گزارش از روی داده‌های ثبت‌شده؛ موجودی همواره از تراکنش‌ها محاسبه می‌شود."""

    def __init__(self, db: Optional[DB] = None) -> None:
        self.db = db or DB()

    def inventory_rows(
        self, category: Optional[str] = None, low_only: bool = False
    ) -> List[Dict[str, object]]:
        """وضعیت فعلی موجودی، محل قفسه، حداقل موجودی و آخرین گردش هر کالا."""
        clauses: List[str] = []
        params: List[object] = []
        if category:
            clauses.append("p.category = ?")
            params.append(category)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.db.all(
            f"""
            SELECT p.code, p.user_code, p.name, p.unit, p.category, p.shelf, p.min_stock,
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
        result: List[Dict[str, object]] = []
        for row in rows:
            stock = float(row["stock"] or 0)
            minimum = float(row["min_stock"] or 0)
            if stock <= 0:
                status = "ناموجود"
            elif minimum > 0 and stock <= minimum:
                status = "کم‌موجودی"
            else:
                status = "عادی"
            if low_only and status == "عادی":
                continue
            result.append({
                "code": row["user_code"] or row["code"],
                "name": row["name"],
                "unit": row["unit"],
                "category": row["category"],
                "shelf": row["shelf"] or "",
                "min_stock": minimum,
                "stock": stock,
                "shortage": max(0.0, minimum - stock),
                "status": status,
                "last_movement": row["last_movement"] or "",
            })
        return result

    def transaction_rows(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        code: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        """تاریخچه گردش کالا؛ بازه تاریخ و کد کالا اختیاری است."""
        start = validate_transaction_date(start_date) if start_date else None
        end = validate_transaction_date(end_date) if end_date else None
        if start and end and start > end:
            raise ValueError("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")
        clauses: List[str] = []
        params: List[object] = []
        if start:
            clauses.append("t.date >= ?")
            params.append(start)
        if end:
            clauses.append("t.date <= ?")
            params.append(end)
        if code:
            clauses.append("t.code = ?")
            params.append(code.strip())
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.db.all(
            f"""
            SELECT t.id, t.date, t.code, p.user_code, p.name, p.unit, t.type, t.qty, t.note
            FROM transactions t
            JOIN products p ON p.code = t.code
            {where}
            ORDER BY t.date DESC, t.id DESC
            """,
            tuple(params),
        )
        labels = {"IN": "ورود", "OUT": "خروج", "RETURN": "عودت"}
        return [{
            "id": int(row["id"]),
            "date": row["date"],
            "code": row["user_code"] or row["code"],
            "name": row["name"],
            "unit": row["unit"],
            "type": labels.get(row["type"], row["type"]),
            "quantity": float(row["qty"]),
            "note": row["note"] or "",
        } for row in rows]

    @staticmethod
    def export_csv(path: str | Path, rows: List[Dict[str, object]]) -> Path:
        """خروجی CSV سازگار با Excel با BOM برای نمایش درست حروف فارسی."""
        target = Path(path)
        if not rows:
            raise ValueError("برای تهیه گزارش، داده‌ای وجود ندارد.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()), extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return target

    def export_inventory_csv(
        self, path: str | Path, category: Optional[str] = None, low_only: bool = False
    ) -> Path:
        return self.export_csv(path, self.inventory_rows(category=category, low_only=low_only))

    def export_transactions_csv(
        self, path: str | Path, start_date: Optional[str] = None,
        end_date: Optional[str] = None, code: Optional[str] = None,
    ) -> Path:
        return self.export_csv(path, self.transaction_rows(start_date, end_date, code))
