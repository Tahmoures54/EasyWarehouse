# -*- coding: utf-8 -*-
"""تست واحد سرویس کالا."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database.db_manager import DB
from app.services.product_service import ProductService


@pytest.fixture
def svc(tmp_path):
    db_file = tmp_path / "t.db"
    return ProductService(DB(path=db_file))


def test_add_and_auto_code(svc):
    p1 = svc.add("دستمال", "جعبه", 10, "مصرفی")
    p2 = svc.add("شامپو", "عدد", 5)
    assert p1.code == "P001"
    assert p2.code == "P002"
    assert svc.get("P001").name == "دستمال"


def test_reject_duplicate_name(svc):
    svc.add("کالای الف")
    with pytest.raises(ValueError, match="قبلاً ثبت"):
        svc.add("کالای الف")


def test_update_and_delete(svc):
    p = svc.add("موقت", "عدد", 1)
    svc.update(p.code, "جدید", "بسته", 8, "عمومی", "A1")
    u = svc.get(p.code)
    assert u.name == "جدید"
    assert u.unit == "بسته"
    assert u.min_stock == 8
    svc.delete(p.code)
    assert svc.get(p.code) is None


def test_list_products(svc):
    svc.add("الف", category="مصرفی")
    svc.add("ب", category="تکنیکال")
    assert len(svc.all()) == 2
    assert len(svc.all("مصرفی")) == 1
    assert len(svc.combo_items()) == 2
