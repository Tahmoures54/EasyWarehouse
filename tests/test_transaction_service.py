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


def test_document_metadata_is_persisted_and_numbered(services):
    ps, ts = services
    product = ps.add("سنددار")
    tx, _ = ts.add(
        product.code, "IN", 4, date_str="2026-10-21", note="رسید خرید",
        party_name="شرکت نمونه", delivered_by="علی", received_by="انباردار",
        reference_no="PO-1405-18",
    )
    assert tx.document_no == f"EW-{tx.id:06d}"
    loaded = ts.get(tx.id)
    assert loaded is not None
    assert loaded.document_no == tx.document_no
    assert loaded.party_name == "شرکت نمونه"
    assert loaded.delivered_by == "علی"
    assert loaded.received_by == "انباردار"
    assert loaded.reference_no == "PO-1405-18"


def test_multi_item_document_shares_number_and_persists_description(services):
    ps, ts = services
    first = ps.add("کالای اول")
    second = ps.add("کالای دوم")
    saved, warnings, document_no = ts.add_document(
        [
            {"code": first.code, "type": "IN", "qty": 5},
            {"code": second.code, "type": "IN", "qty": 3},
        ],
        date_str="2026-10-21",
        note="رسید خرید ماهانه",
        party_name="تأمین‌کننده",
        delivered_by="علی",
        received_by="انباردار",
        reference_no="PO-100",
    )
    assert not warnings
    assert len(saved) == 2
    assert {tx.document_no for tx in saved} == {document_no}
    assert ps.get(first.code).stock == 5
    assert ps.get(second.code).stock == 3
    rows = ts.db.all(
        "SELECT document_id, document_no, note FROM transactions ORDER BY id"
    )
    assert len({row["document_id"] for row in rows}) == 1
    assert all(row["document_no"] == document_no for row in rows)
    assert all(row["note"] == "رسید خرید ماهانه" for row in rows)


def test_multi_item_document_is_atomic_when_one_line_fails(services):
    ps, ts = services
    first = ps.add("کالای موجود")
    second = ps.add("کالای ناکافی")
    ts.add(first.code, "IN", 4)
    ts.add(second.code, "IN", 1)
    before = ts.count()
    with pytest.raises(ValueError, match="کل سند"):
        ts.add_document([
            {"code": first.code, "type": "OUT", "qty": 2},
            {"code": second.code, "type": "OUT", "qty": 5},
        ], allow_overdraw=False)
    assert ts.count() == before
    assert ps.get(first.code).stock == 4
    assert ps.get(second.code).stock == 1


def test_document_rejects_mixed_movement_types(services):
    ps, ts = services
    first = ps.add("کالای ورود")
    second = ps.add("کالای خروج")
    with pytest.raises(ValueError, match="نوع همه اقلام"):
        ts.add_document([
            {"code": first.code, "type": "IN", "qty": 1},
            {"code": second.code, "type": "OUT", "qty": 1},
        ])


def test_jalali_date_round_trip():
    assert from_jalali("1405/07/29") == "2026-10-21"
    assert to_jalali("2026-10-21") == "1405/07/29"
    assert from_jalali("۱۴۰۵/۰۷/۲۹") == "2026-10-21"
    assert today_jalali() == to_jalali(__import__("datetime").date.today().isoformat())


def test_invalid_jalali_date_rejected():
    for value in ("1405/13/01", "1405/12/30", "1405/07/xx", ""):
        with pytest.raises(ValueError):
            from_jalali(value)


def test_void_document_preserves_original_lines_and_records_reversal(services):
    ps, ts = services
    p1 = ps.add("کالای اول")
    p2 = ps.add("کالای دوم")
    ts.add(p1.code, "IN", 10, "2026-10-01")
    ts.add(p2.code, "IN", 12, "2026-10-01")
    original, _, document_no = ts.add_document([
        {"code": p1.code, "type": "OUT", "qty": 3},
        {"code": p2.code, "type": "OUT", "qty": 4},
    ], date_str="2026-10-02")
    before_ids = [tx.id for tx in original]
    reversal_no = ts.void_document(document_no, "admin", "ثبت اشتباه")
    assert ps.get(p1.code).stock == 10
    assert ps.get(p2.code).stock == 12
    assert [tx.id for tx in ts.document_lines(before_ids[0])] == before_ids
    original_doc = ts.db.one("SELECT status FROM warehouse_documents WHERE document_no=?",
                             (document_no,))
    assert original_doc["status"] == "VOID"
    reversal = ts.db.one("SELECT reference_no FROM warehouse_documents WHERE document_no=?",
                         (reversal_no,))
    assert reversal["reference_no"] == document_no
    event = ts.db.one("SELECT event, details FROM audit_log ORDER BY id DESC LIMIT 1")
    assert event["event"] == "warehouse_document_voided"
    assert "ثبت اشتباه" in event["details"]
    with pytest.raises(ValueError, match="قبلاً ابطال"):
        ts.void_document(document_no, "admin", "تلاش مجدد")


def test_void_document_requires_reason_and_keeps_stock_unchanged(services):
    ps, ts = services
    product = ps.add("کالای تست")
    _, _, document_no = ts.add_document([
        {"code": product.code, "type": "IN", "qty": 2},
    ], date_str="2026-10-01")
    with pytest.raises(ValueError, match="علت"):
        ts.void_document(document_no, "admin", " ")
    assert ps.get(product.code).stock == 2
