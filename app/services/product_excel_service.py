# -*- coding: utf-8 -*-
"""ساخت الگوی Excel و ورود امن گروهی کالاها."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from app.config import CATEGORIES, PRODUCT_CODE_PADDING, PRODUCT_CODE_PREFIX, UNITS
from app.services.product_service import ProductService

HEADERS = ("نام کالا", "واحد", "حداقل موجودی", "دسته", "قفسه")
DEFAULT_UNIT = "عدد"
DEFAULT_CATEGORY = "عمومی"


def create_product_template(path: str | Path) -> Path:
    """Create a formatted .xlsx template with instructions and cell validation."""
    target = Path(path)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "فهرست کالاها"
    sheet.sheet_view.rightToLeft = True
    sheet.append(HEADERS)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:E1000"
    sheet.row_dimensions[1].height = 28
    for cell in sheet[1]:
        cell.font = Font(name="Tahoma", bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="102A43")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for col, width in {"A": 30, "B": 16, "C": 20, "D": 18, "E": 20}.items():
        sheet.column_dimensions[col].width = width
    sheet.append([None, None, None, None, None])
    sheet["A2"].comment = Comment(
        "این ردیف نمونه نیست؛ اطلاعات کالای واقعی را در آن وارد کنید یا ردیف را خالی بگذارید.",
        "EasyWarehouse",
    )
    units = DataValidation(type="list", formula1='"' + ",".join(UNITS) + '"', allow_blank=True)
    categories = DataValidation(type="list", formula1='"' + ",".join(CATEGORIES) + '"', allow_blank=True)
    minimum = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True)
    for validation, message, cell_range in (
        (units, "واحد را از فهرست انتخاب کنید.", "B2:B1000"),
        (categories, "دسته را از فهرست انتخاب کنید.", "D2:D1000"),
        (minimum, "حداقل موجودی باید صفر یا بیشتر باشد.", "C2:C1000"),
    ):
        validation.error = message
        sheet.add_data_validation(validation)
        validation.add(cell_range)
    guide = workbook.create_sheet("راهنما")
    guide.sheet_view.rightToLeft = True
    guide.column_dimensions["A"].width = 28
    guide.column_dimensions["B"].width = 90
    guide.append(["ستون", "راهنما"])
    guidance = [
        ("نام کالا", "اجباری؛ نام کالا باید یکتا باشد."),
        ("واحد", "اختیاری؛ اگر خالی باشد «عدد» ثبت می‌شود."),
        ("حداقل موجودی", "اختیاری؛ عدد صفر یا مثبت. پیش‌فرض صفر."),
        ("دسته", "اختیاری؛ مصرفی، تکنیکال یا عمومی. پیش‌فرض عمومی."),
        ("قفسه", "اختیاری؛ محل نگهداری کالا."),
        ("کد کالا", "در فایل وارد نمی‌شود؛ برنامه کد یکتا را خودکار تولید می‌کند."),
        ("موجودی اولیه", "از فایل وارد نمی‌شود و صفر است؛ گردش ورود را از فرم اصلی ثبت کنید."),
        ("ورود گروهی", "ردیف‌های نامعتبر یا کالاهای تکراری رد می‌شوند؛ ردیف‌های معتبر پس از تأیید وارد می‌شوند."),
    ]
    for row in guidance:
        guide.append(row)
    for cell in guide[1]:
        cell.font = Font(name="Tahoma", bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="102A43")
    for row in guide.iter_rows():
        for cell in row:
            cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
            if cell.row > 1:
                cell.font = Font(name="Tahoma", size=10, bold=(cell.column == 1))
    guide.freeze_panes = "A2"
    target.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(target)
    return target


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def preview_product_import(path: str | Path, service: ProductService):
    """Return valid rows, validation errors, and count of nonblank rows."""
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"فایل Excel قابل خواندن نیست: {exc}") from exc
    try:
        sheet = workbook["فهرست کالاها"] if "فهرست کالاها" in workbook.sheetnames else workbook.active
        iterator = sheet.iter_rows(values_only=True)
        header = next(iterator, None)
        normalized = [_text(value) for value in (header or ())]
        positions = {name: normalized.index(name) for name in HEADERS if name in normalized}
        if "نام کالا" not in positions:
            raise ValueError("ستون «نام کالا» در ردیف اول فایل پیدا نشد. از الگوی رسمی برنامه استفاده کنید.")
        existing_names = {p.name.casefold() for p in service.all()}
        accepted_names: set[str] = set()
        valid: list[dict[str, Any]] = []
        errors: list[str] = []
        total_rows = 0
        for excel_row, values in enumerate(iterator, start=2):
            values = values or ()
            if not any(_text(value) for value in values):
                continue
            total_rows += 1

            def get(column: str, default: Any = "") -> Any:
                index = positions.get(column)
                return values[index] if index is not None and index < len(values) else default

            name = _text(get("نام کالا"))
            unit = _text(get("واحد", DEFAULT_UNIT)) or DEFAULT_UNIT
            category = _text(get("دسته", DEFAULT_CATEGORY)) or DEFAULT_CATEGORY
            shelf = _text(get("قفسه"))
            raw_min = get("حداقل موجودی", 0)
            try:
                minimum = 0.0 if raw_min is None or _text(raw_min) == "" else float(str(raw_min).replace(",", "."))
            except (TypeError, ValueError):
                errors.append(f"ردیف {excel_row}: حداقل موجودی باید عدد باشد.")
                continue
            if not name:
                errors.append(f"ردیف {excel_row}: نام کالا خالی است.")
                continue
            if not math.isfinite(minimum) or minimum < 0:
                errors.append(f"ردیف {excel_row}: حداقل موجودی باید عددی متناهی و غیرمنفی باشد.")
                continue
            if unit not in UNITS:
                errors.append(f"ردیف {excel_row}: واحد «{unit}» معتبر نیست؛ از فهرست الگو انتخاب کنید.")
                continue
            if category not in CATEGORIES:
                errors.append(f"ردیف {excel_row}: دسته «{category}» معتبر نیست.")
                continue
            key = name.casefold()
            if key in existing_names or key in accepted_names:
                errors.append(f"ردیف {excel_row}: کالای «{name}» تکراری است.")
                continue
            accepted_names.add(key)
            valid.append({
                "name": name, "unit": unit, "min_stock": minimum,
                "category": category, "shelf": shelf, "excel_row": excel_row,
            })
        return valid, errors, total_rows
    finally:
        workbook.close()


def import_product_rows(service: ProductService, rows: list[dict[str, Any]]) -> int:
    """Insert validated rows atomically and generate unique product codes."""
    if not rows:
        return 0
    prefix, padding = PRODUCT_CODE_PREFIX, PRODUCT_CODE_PADDING
    with service.db.transaction() as conn:
        existing = {str(row["name"]).casefold() for row in conn.execute("SELECT name FROM products")}
        names: set[str] = set()
        for item in rows:
            key = item["name"].strip().casefold()
            if not key or key in existing or key in names:
                raise ValueError(f"نام کالا «{item.get('name', '')}» تکراری است؛ فایل را دوباره بررسی کنید.")
            if not math.isfinite(float(item["min_stock"])) or float(item["min_stock"]) < 0:
                raise ValueError(f"حداقل موجودی کالای «{item['name']}» نامعتبر است.")
            names.add(key)
        codes = [str(row["code"]) for row in conn.execute("SELECT code FROM products")]
        numbers = []
        for code in codes:
            if code.startswith(prefix):
                try:
                    numbers.append(int(code[len(prefix):]))
                except ValueError:
                    pass
        next_number = max(numbers, default=0) + 1
        for item in rows:
            code = f"{prefix}{next_number:0{padding}d}"
            next_number += 1
            conn.execute(
                "INSERT INTO products (code, name, unit, min_stock, category, shelf) VALUES (?, ?, ?, ?, ?, ?)",
                (code, item["name"].strip(), item["unit"], float(item["min_stock"]),
                 item["category"], item["shelf"]),
            )
    return len(rows)
