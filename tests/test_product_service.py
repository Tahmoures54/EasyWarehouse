# -*- coding: utf-8 -*-
"""تست واحد سرویس کالا."""

from __future__ import annotations

import sys
import sqlite3
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


def test_duplicate_name_and_user_code_are_warnings_not_blockers(svc):
    first = svc.add("آب معدنی", user_code="10025")
    second = svc.add("آب معدنی", user_code="10080")
    third = svc.add("نوشیدنی", user_code="10025")
    assert first.code != second.code
    assert second.user_code == "10080"
    assert len(svc.all()) == 3
    assert any("کد" in warning for warning in svc.duplicate_warnings("نوشیدنی", "10025"))
    assert any("نام" in warning for warning in svc.duplicate_warnings("آب معدنی", "20000"))
    assert svc.normalize_name(" آب  معدني ") == svc.normalize_name("آب معدنی")


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


@pytest.mark.parametrize("bad_minimum", [-1, float("nan"), float("inf"), "not-a-number"])
def test_reject_invalid_minimum_stock(svc, bad_minimum):
    with pytest.raises(ValueError):
        svc.add("حداقل نامعتبر", min_stock=bad_minimum)


def test_legacy_database_migration_preserves_transactions_and_allows_duplicate_names(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE products (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            unit TEXT NOT NULL DEFAULT 'عدد',
            min_stock REAL NOT NULL DEFAULT 0,
            category TEXT NOT NULL DEFAULT 'عمومی',
            shelf TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('IN','OUT','RETURN')),
            qty REAL NOT NULL CHECK(qty > 0),
            date TEXT NOT NULL,
            note TEXT,
            FOREIGN KEY(code) REFERENCES products(code)
        );
        INSERT INTO products(code, name, unit, min_stock) VALUES ('P001', 'آب معدنی', 'عدد', 1);
        INSERT INTO transactions(code, type, qty, date) VALUES ('P001', 'IN', 3, '2026-10-19');
    """)
    conn.commit()
    conn.close()

    migrated = ProductService(DB(path=path))
    original = migrated.get("P001")
    assert original.user_code == "P001"
    assert original.stock == 3
    second = migrated.add("آب معدنی", user_code="10080")
    assert second.user_code == "10080"
    assert migrated.get("P001").stock == 3
    assert migrated.get(second.code).stock == 0
    with sqlite3.connect(path) as check:
        assert check.execute("PRAGMA foreign_key_check").fetchall() == []


def test_migrated_products_table_retains_structural_checks(tmp_path):
    path = tmp_path / "legacy-checks.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE products (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            unit TEXT NOT NULL DEFAULT 'عدد',
            min_stock REAL NOT NULL DEFAULT 0,
            category TEXT NOT NULL DEFAULT 'عمومی',
            shelf TEXT NOT NULL DEFAULT ''
        );
        INSERT INTO products(code, name, min_stock, category)
        VALUES ('P001', 'کالای قدیمی', -3, 'دسته قدیمی');
    """)
    conn.commit()
    conn.close()

    DB(path=path)  # مهاجرت باید داده قدیمی ناسازگار را به مقدار معتبر تبدیل کند.
    with sqlite3.connect(path) as check:
        row = check.execute(
            "SELECT min_stock, category FROM products WHERE code='P001'"
        ).fetchone()
        assert row == (0.0, "عمومی")
        with pytest.raises(sqlite3.IntegrityError):
            check.execute(
                "INSERT INTO products(code, name, min_stock) VALUES ('BAD1', 'نامعتبر', -1)"
            )
        with pytest.raises(sqlite3.IntegrityError):
            check.execute(
                "INSERT INTO products(code, name, category) VALUES ('BAD2', 'دسته نامعتبر', 'غلط')"
            )
        with pytest.raises(sqlite3.IntegrityError):
            check.execute(
                "INSERT INTO products(code, name) VALUES ('BAD3', '   ')"
            )
