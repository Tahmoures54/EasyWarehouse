# -*- coding: utf-8 -*-
"""آزمون‌های قالب چاپ رسید و حواله."""

from types import SimpleNamespace

from app.services.print_service import build_voucher_html


def _tx(type_="IN", note="تحویل <آزمایشی>"):
    return SimpleNamespace(
        id=17,
        type=type_,
        date="2026-10-21",
        code="internal-1",
        user_code="A-17",
        name='پیچ و مهره "نمونه"',
        qty=2.5,
        unit="بسته",
        note=note,
        type_fa=lambda: {"IN": "ورود", "OUT": "خروج", "RETURN": "عودت"}[type_],
    )


def test_receipt_print_contains_persian_date_and_document_number():
    html = build_voucher_html(_tx("IN"), "اپراتور")
    assert "رسید ورود کالا" in html
    assert "EW-000017" in html
    assert "1405/07/29" in html
    assert "A-17" in html
    assert "اپراتور" in html


def test_outgoing_transaction_is_dispatch_voucher():
    html = build_voucher_html(_tx("OUT"))
    assert "حواله خروج کالا" in html
    assert "تحویل‌گیرنده" in html
    assert "چاپ / ذخیره PDF" in html


def test_html_escapes_user_supplied_values():
    html = build_voucher_html(_tx("RETURN", "<script>alert(1)</script>"))
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "رسید عودت کالا" in html
