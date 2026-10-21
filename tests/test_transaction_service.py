# -*- coding: utf-8 -*-
"""تست واحد سرویس تراکنش."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database.db_manager import DB
from app.services.product_service import ProductService
from app.services.transaction_service import TransactionService, parse_positive_qty
from app.utils.date_utils import from_jalali, to_jalali, today_jalali


@pytest.fixture
def services(tmp_path):
    db = DB(path=tmp_path / "t.db")
    return ProductService(db), TransactionService(db)


def test_in_increases_stock(services):
    ps, ts = services
    p = ps.add("کالا", min_stock=5)
    ts.add(p.code, "IN", 10)
    assert ps.get(p.code).stock == 10


def test_out_decreases_stock(services):
    ps, ts = services
    p = ps.add("کالا")
    ts.add(p.code, "IN", 10)
    ts.add(p.code, "OUT", 3)
    assert ps.get(p.code).stock == 7


def test_return_increases_stock(services):
    ps, ts = services
    p = ps.add("کالا")
    ts.add(p.code, "IN", 10)
    ts.add(p.code, "OUT", 4)
    ts.add(p.code, "RETURN", 2)
    assert ps.get(p.code).stock == 8


def test_negative_stock_scenario(services):
    ps, ts = services
    p = ps.add("بحرانی", min_stock=0)
    ts.add(p.code, "IN", 2)
    _, warn = ts.add(p.code, "OUT", 5, allow_overdraw=True)
    assert warn is not None
    assert "منفی" in warn
    assert ps.get(p.code).stock == -3


def test_min_stock_warning(services):
    ps, ts = services
    p = ps.add("حساس", min_stock=10)
    ts.add(p.code, "IN", 12)
    _, warn = ts.add(p.code, "OUT", 5)
    assert warn is not None
    assert "حداقل" in warn


def test_overdraw_blocked_when_not_allowed(services):
    ps, ts = services
    p = ps.add("محدود")
    ts.add(p.code, "IN", 3)
    with pytest.raises(ValueError):
        ts.add(p.code, "OUT", 10, allow_overdraw=False)


def test_date_order(services):
    ps, ts = services
    p = ps.add("کالا")
    ts.add(p.code, "IN", 1, date_str="2026-01-01")
    ts.add(p.code, "IN", 2, date_str="2026-01-03")
    ts.add(p.code, "OUT", 1, date_str="2026-01-02")
    items = ts.all()
    dates = [t.date for t in items]
    assert dates == sorted(dates, reverse=True)


def test_parse_qty():
    assert parse_positive_qty("12") == 12
    assert parse_positive_qty("1.5") == 1.5
    with pytest.raises(ValueError):
        parse_positive_qty("abc")
    with pytest.raises(ValueError):
        parse_positive_qty("-1")
    with pytest.raises(ValueError):
        parse_positive_qty("0")


def test_full_flow(services):
    ps, ts = services
    p = ps.add("جریان کامل", "عدد", 5, "مصرفی")
    ts.add(p.code, "IN", 20)
    ts.add(p.code, "OUT", 7)
    ts.add(p.code, "RETURN", 2)
    assert ps.get(p.code).stock == 15



def test_overdraw_is_blocked_by_default(services):
    ps, ts = services
    p = ps.add("پیش‌فرض امن")
    ts.add(p.code, "IN", 2)
    with pytest.raises(ValueError, match="ثبت خروج انجام نشد"):
        ts.add(p.code, "OUT", 3)
    assert ps.get(p.code).stock == 2


@pytest.mark.parametrize("bad_date", ["19-10-2026", "2026-02-30", "2026-1-01", "2026/10/19", ""])
def test_invalid_nonempty_dates_rejected(services, bad_date):
    ps, ts = services
    p = ps.add("تاریخ نامعتبر")
    with pytest.raises(ValueError, match="تاریخ"):
        ts.add(p.code, "IN", 1, date_str=bad_date)


def test_delete_transaction_recalculates_stock(services):
    ps, ts = services
    p = ps.add("حذف تراکنش")
    tx, _ = ts.add(p.code, "IN", 8)
    assert ps.get(p.code).stock == 8
    ts.delete(tx.id)
    assert ps.get(p.code).stock == 0


def test_non_finite_quantity_rejected(services):
    ps, ts = services
    p = ps.add("عدد نامعتبر")
    for value in (float("nan"), float("inf"), -float("inf"), 0):
        with pytest.raises(ValueError):
            ts.add(p.code, "IN", value)


def test_foreign_keys_are_enabled_for_every_connection(services):
    ps, _ = services
    db = ps.db
    with db.transaction() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO transactions (code, type, qty, date) VALUES (?, ?, ?, ?)",
                ("MISSING", "IN", 1, "2026-10-19"),
            )


def test_jalali_date_round_trip():
    assert from_jalali("1405/07/29") == "2026-10-21"
    assert to_jalali("2026-10-21") == "1405/07/29"
    assert from_jalali("۱۴۰۵/۰۷/۲۹") == "2026-10-21"
    assert today_jalali() == to_jalali(__import__("datetime").date.today().isoformat())


def test_invalid_jalali_date_rejected():
    for value in ("1405/13/01", "1405/12/30", "1405/07/xx", ""):
        with pytest.raises(ValueError):
            from_jalali(value)
