# -*- coding: utf-8 -*-
"""آزمون‌های پشتیبان‌گیری و بازیابی."""
import sqlite3
import pytest
from app.database.db_manager import DB
from app.services.backup_service import BackupService
from app.services.product_service import ProductService

def make_db(path, product_name):
    db = DB(path=path)
    ProductService(db).add(product_name)
    return db

def test_valid_backup_and_restore(tmp_path):
    current = tmp_path / "anbar.db"
    make_db(current, "کالای فعلی")
    service = BackupService(current)
    saved = service.backup(tmp_path / "backups")
    assert saved.is_file() and saved.stat().st_size > 0
    ProductService(DB(path=current)).add("کالای جدید")
    service.restore(saved)
    restored = ProductService(DB(path=current))
    assert restored.count() == 1
    assert restored.get("P001").name == "کالای فعلی"
    assert list(tmp_path.glob("anbar.db.pre_restore_*.bak"))

@pytest.mark.parametrize("kind", ["corrupt", "empty"])
def test_invalid_backup_never_replaces_current_database(tmp_path, kind):
    current = tmp_path / "anbar.db"
    make_db(current, "داده سالم")
    candidate = tmp_path / "bad.db"
    candidate.write_bytes(b"not a sqlite database" if kind == "corrupt" else b"")
    with pytest.raises(ValueError):
        BackupService(current).restore(candidate)
    assert ProductService(DB(path=current)).get("P001").name == "داده سالم"
    assert not list(tmp_path.glob("anbar.db.pre_restore_*.bak"))

def test_backup_requires_expected_warehouse_schema(tmp_path):
    current = tmp_path / "anbar.db"
    make_db(current, "داده سالم")
    other = tmp_path / "other.db"
    with sqlite3.connect(other) as conn:
        conn.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
    with pytest.raises(ValueError, match="ساختار"):
        BackupService(current).restore(other)
    assert ProductService(DB(path=current)).get("P001").name == "داده سالم"

def test_restore_missing_file_keeps_current_database(tmp_path):
    current = tmp_path / "anbar.db"
    make_db(current, "داده سالم")
    with pytest.raises(FileNotFoundError):
        BackupService(current).restore(tmp_path / "missing.db")
    assert ProductService(DB(path=current)).get("P001").name == "داده سالم"
