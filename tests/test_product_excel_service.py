# -*- coding: utf-8 -*-
"""تست‌های ساخت الگو و ورود Excel کالاها."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database.db_manager import DB
from app.services.product_service import ProductService
from app.services.product_excel_service import (
    create_product_template,
    import_product_rows,
    preview_product_import,
)


@pytest.fixture
def service(tmp_path):
    return ProductService(DB(path=tmp_path / "products.db"))


def test_template_has_persian_headers_and_instructions(tmp_path):
    from openpyxl import load_workbook

    path = create_product_template(tmp_path / "template.xlsx")
    workbook = load_workbook(path, read_only=True, data_only=True)
    assert workbook["فهرست کالاها"]["A1"].value == "نام کالا"
    assert workbook["فهرست کالاها"]["B1"].value == "واحد"
    assert "راهنما" in workbook.sheetnames
    assert workbook["فهرست کالاها"]["A2"].value is None
    workbook.close()


def test_preview_rejects_duplicates_and_invalid_rows(tmp_path, service):
    from openpyxl import Workbook

    service.add("کالای موجود")
    path = tmp_path / "input.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "فهرست کالاها"
    sheet.append(["نام کالا", "واحد", "حداقل موجودی", "دسته", "قفسه"])
    sheet.append(["کالای جدید", "عدد", 5, "مصرفی", "A1"])
    sheet.append(["کالای موجود", "عدد", 0, "عمومی", ""])
    sheet.append(["کالای جدید", "عدد", 2, "عمومی", ""])
    sheet.append(["موجودی بد", "عدد", -1, "عمومی", ""])
    sheet.append(["واحد بد", "غیرمجاز", 0, "عمومی", ""])
    workbook.save(path)
    workbook.close()

    rows, errors, total = preview_product_import(path, service)
    assert total == 5
    assert [row["name"] for row in rows] == ["کالای جدید"]
    assert len(errors) == 4


def test_import_is_atomic_and_generates_codes(tmp_path, service):
    rows = [
        {"name": "کالای یک", "unit": "عدد", "min_stock": 1, "category": "عمومی", "shelf": ""},
        {"name": "کالای دو", "unit": "جعبه", "min_stock": 2, "category": "مصرفی", "shelf": "B2"},
    ]
    assert import_product_rows(service, rows) == 2
    assert service.get("P001").name == "کالای یک"
    assert service.get("P002").name == "کالای دو"
    assert service.get("P002").stock == 0

    duplicate_rows = [
        {"name": "کالای سه", "unit": "عدد", "min_stock": 0, "category": "عمومی", "shelf": ""},
        {"name": "کالای یک", "unit": "عدد", "min_stock": 0, "category": "عمومی", "shelf": ""},
    ]
    with pytest.raises(ValueError, match="تکراری"):
        import_product_rows(service, duplicate_rows)
    assert service.get("P003") is None
