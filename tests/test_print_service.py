# -*- coding: utf-8 -*-
"""آزمون‌های قالب چاپ رسید و حواله."""

from types import SimpleNamespace

from app.services.print_service import build_document_html, build_kardex_html, build_voucher_html


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
        document_no="EW-000017",
        party_name="تأمین‌کننده نمونه",
        delivered_by="علی",
        received_by="انباردار",
        reference_no="PO-17",
        type_fa=lambda: {"IN": "ورود", "OUT": "خروج", "RETURN": "عودت"}[type_],
    )


def test_receipt_print_contains_persian_date_and_document_number():
    html = build_voucher_html(_tx("IN"), "اپراتور")
    assert "رسید ورود کالا" in html
    assert "EW-000017" in html
    assert "1405/07/29" in html
    assert "A-17" in html
    assert "اپراتور" in html
    assert "تأمین‌کننده نمونه" in html
    assert "تحویل‌دهنده" in html
    assert "تحویل‌گیرنده" in html
    assert "PO-17" in html
    assert "function(){ window.print(); }" in html
    assert "function(){{" not in html


def test_multi_item_document_prints_shared_header_and_all_lines():
    first = _tx("IN")
    second = _tx("IN")
    second.id = 18
    second.code = "internal-2"
    second.user_code = "A-18"
    second.name = "واشر"
    second.qty = 6
    html = build_document_html([first, second], "اپراتور")
    assert "EW-000017" in html
    assert "توضیحات" in html
    assert "تحویل‌دهنده" in html
    assert "پیچ و مهره" in html
    assert "واشر" in html
    assert "A-18" in html
    assert html.count("<tr>") >= 10


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


def test_kardex_print_filters_rows_and_escapes_text():
    product = SimpleNamespace(code="P-1", user_code="P-1", name="کالا <نمونه>", unit="عدد")
    rows = [
        {"id": "", "document_no": "", "date": "2026-10-01", "type": "مانده ابتدای دوره", "incoming": 0, "outgoing": 0, "balance": 8, "unit": "عدد", "note": ""},
        {"id": 1, "document_no": "EW-000001", "date": "2026-10-02", "type": "ورود", "incoming": 5, "outgoing": 0, "balance": 13, "unit": "عدد", "note": "رسید خرید"},
        {"id": 2, "document_no": "EW-000002", "date": "2026-10-03", "type": "خروج", "incoming": 0, "outgoing": 2, "balance": 11, "unit": "عدد", "note": "<script>bad()</script>"},
    ]
    html = build_kardex_html(product, rows, "1405/07/10", "1405/07/12", "خروج")
    assert "کاردکس کالا" in html
    assert "EW-000002" in html
    assert "EW-000001" not in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html
    assert "<script>bad()</script>" not in html
    assert "&lt;نمونه&gt;" in html
    assert "مانده پایان دوره: 11" in html
