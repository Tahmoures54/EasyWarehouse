# -*- coding: utf-8 -*-
"""قالب چاپ رسید ورود و حواله خروج؛ بدون وابستگی اضافی و مناسب چاپ/PDF."""

from __future__ import annotations

import html
import logging
import webbrowser
from pathlib import Path
from typing import Mapping, Any

from app.config import get_db_path
from app.utils.date_utils import to_jalali

logger = logging.getLogger(__name__)


def _safe(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def build_voucher_html(tx, operator: str = "") -> str:
    """ساخت HTML مستقل و قابل چاپ از یک تراکنش ثبت‌شده."""
    if tx is None or not getattr(tx, "id", None):
        raise ValueError("برای چاپ، تراکنش ثبت‌شده و معتبر لازم است.")

    labels = {"IN": ("رسید ورود کالا", "رسید انبار"), "OUT": ("حواله خروج کالا", "حواله انبار"),
              "RETURN": ("رسید عودت کالا", "رسید عودت")}
    title, doc_label = labels.get(tx.type, ("سند گردش کالا", "سند انبار"))
    try:
        shown_date = to_jalali(tx.date)
    except (TypeError, ValueError):
        shown_date = tx.date

    fields = [
        ("شماره سند", f"EW-{int(tx.id):06d}"),
        ("تاریخ", shown_date),
        ("نوع عملیات", tx.type_fa()),
        ("کد کالا", getattr(tx, "user_code", "") or tx.code),
        ("نام کالا", tx.name or "—"),
        ("مقدار", f"{tx.qty:g} {tx.unit or ''}".strip()),
        ("توضیحات", tx.note or "—"),
        ("ثبت‌کننده", operator or "—"),
    ]
    rows = "\n".join(
        f"<tr><th>{_safe(label)}</th><td>{_safe(value)}</td></tr>"
        for label, value in fields
    )
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_safe(title)} - EW-{int(tx.id):06d}</title>
<style>
@page {{ size: A4 portrait; margin: 14mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Tahoma, Arial, sans-serif; color: #17212b; margin: 0; font-size: 12pt; }}
.sheet {{ max-width: 190mm; margin: 0 auto; }}
header {{ border-bottom: 3px solid #087f8c; padding: 0 0 12px; margin-bottom: 22px; }}
.brand {{ font-size: 11pt; color: #087f8c; font-weight: bold; }}
h1 {{ font-size: 21pt; margin: 10px 0 4px; }}
.sub {{ color: #596775; font-size: 10pt; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
th, td {{ border: 1px solid #cbd5df; padding: 11px 12px; text-align: right; vertical-align: top; }}
th {{ width: 29%; background: #f1f6f8; }}
.signatures {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 58px; }}
.signature {{ border-top: 1px solid #718096; padding-top: 9px; min-height: 55px; text-align: center; }}
.footer {{ margin-top: 26px; border-top: 1px solid #cbd5df; padding-top: 9px; font-size: 9pt; color: #64748b; }}
.actions {{ margin: 14px auto; max-width: 190mm; display: flex; gap: 8px; }}
button {{ border: 0; border-radius: 5px; padding: 10px 16px; cursor: pointer; background: #087f8c; color: white; font: inherit; }}
@media print {{ .actions {{ display: none; }} }}
</style>
</head>
<body>
<div class="actions"><button onclick="window.print()">چاپ / ذخیره PDF</button></div>
<main class="sheet">
<header><div class="brand">انبارداری آسان | مدیریت انبار</div>
<h1>{_safe(title)}</h1><div class="sub">{_safe(doc_label)} · سند قابل ردیابی بر اساس گردش ثبت‌شده</div></header>
<table><tbody>{rows}</tbody></table>
<section class="signatures">
<div class="signature">تحویل‌دهنده<br><br>نام و امضا</div>
<div class="signature">تحویل‌گیرنده / مسئول انبار<br><br>نام و امضا</div>
</section>
<div class="footer">این سند از گردش ثبت‌شده در انبارداری آسان تولید شده است. شماره سند از شناسه داخلی گردش ساخته شده و در دیتابیس تغییر ایجاد نمی‌کند.</div>
</main>
<script>window.addEventListener('load', function(){{ setTimeout(function(){{ window.print(); }}, 350); }});</script>
</body></html>"""


def print_transaction(tx, operator: str = "") -> Path:
    """ذخیره قالب چاپ در پوشه داده کاربر و بازکردن آن در مرورگر پیش‌فرض."""
    folder = get_db_path().parent / "printouts"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"EW-{int(tx.id):06d}.html"
    path.write_text(build_voucher_html(tx, operator), encoding="utf-8")
    opened = webbrowser.open(path.resolve().as_uri())
    if not opened:
        logger.warning("Voucher saved but browser did not report successful open: %s", path)
    return path



def build_kardex_html(product, rows, start_label: str = "", end_label: str = "", movement_filter: str = "همه گردش‌ها") -> str:
    """ساخت گزارش HTML چاپ‌پذیر کاردکس با escape کردن متن‌های ورودی."""
    if product is None:
        raise ValueError("برای چاپ کاردکس باید کالا انتخاب شود.")
    product_code = getattr(product, "user_code", "") or getattr(product, "code", "")
    product_name = getattr(product, "name", "")
    unit = getattr(product, "unit", "")
    opening_row = next((r for r in rows if r.get("type") == "مانده ابتدای دوره"), None)
    all_movements = [r for r in rows if r.get("type") != "مانده ابتدای دوره"]
    visible_rows = [r for r in rows if r.get("type") == "مانده ابتدای دوره" or movement_filter == "همه گردش‌ها" or r.get("type") == movement_filter]
    body_rows = []
    for row in visible_rows:
        try:
            shown_date = to_jalali(row.get("date", "")) if row.get("date") else ""
        except (TypeError, ValueError):
            shown_date = row.get("date", "")
        values = (
            row.get("document_no", ""), shown_date, row.get("type", ""),
            f'{row.get("incoming", 0):g}', f'{row.get("outgoing", 0):g}',
            f'{row.get("balance", 0):g}', row.get("unit", unit), row.get("note", "")
        )
        body_rows.append("<tr>" + "".join(f"<td>{_safe(value)}</td>" for value in values) + "</tr>")
    table_rows = "\n".join(body_rows) or '<tr><td colspan="8">گردشی برای نمایش وجود ندارد.</td></tr>'
    opening = opening_row.get("balance", 0) if opening_row else 0
    total_in = sum(float(r.get("incoming", 0) or 0) for r in all_movements)
    total_out = sum(float(r.get("outgoing", 0) or 0) for r in all_movements)
    ending = rows[-1].get("balance", opening) if rows else opening
    return f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>کاردکس {_safe(product_name)}</title><style>
@page {{ size:A4 landscape; margin:10mm; }} body{{font-family:Tahoma,Arial,sans-serif;color:#17212b;font-size:10pt}}
h1{{font-size:18pt;margin-bottom:6px}} .meta{{margin:8px 0 14px;line-height:1.9}}
table{{width:100%;border-collapse:collapse}} th,td{{border:1px solid #b8c5ce;padding:6px;text-align:right;vertical-align:top}}
th{{background:#edf4f6}} .summary{{margin:12px 0;padding:10px;border:1px solid #cbd5df;line-height:1.9}}
button{{padding:8px 14px;background:#087f8c;color:white;border:0;font:inherit;cursor:pointer}}
@media print{{button{{display:none}}}}
</style></head><body><button onclick="window.print()">چاپ / ذخیره PDF</button>
<h1>گزارش کاردکس کالا</h1>
<div class="meta">کد کالا: {_safe(product_code)} | نام کالا: {_safe(product_name)} | واحد: {_safe(unit)}<br>
از تاریخ: {_safe(start_label or "ابتدای سابقه")} | تا تاریخ: {_safe(end_label or "بدون محدودیت")} | فیلتر گردش: {_safe(movement_filter)}</div>
<div class="summary">مانده ابتدای دوره: {opening:g} {_safe(unit)} | جمع ورود کل دوره: {total_in:g} | جمع خروج کل دوره: {total_out:g} | مانده پایان دوره: {ending:g} {_safe(unit)}</div>
<table><thead><tr><th>شماره سند</th><th>تاریخ</th><th>شرح</th><th>ورود</th><th>خروج</th><th>مانده</th><th>واحد</th><th>توضیحات</th></tr></thead>
<tbody>{table_rows}</tbody></table><p>گزارش تولیدشده توسط انبارداری آسان؛ چاپ یا ذخیره PDF از طریق مرورگر انجام می‌شود.</p>
</body></html>"""


__all__ = ["build_voucher_html", "build_kardex_html", "print_transaction"]
