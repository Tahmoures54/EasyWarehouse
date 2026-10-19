from app.database.db_manager import DB
from app.services.product_service import ProductService
from app.services.report_service import ReportService
from app.services.transaction_service import TransactionService


def _services(tmp_path):
    db = DB(tmp_path / "test.db")
    products = ProductService(db)
    transactions = TransactionService(db)
    reports = ReportService(db)
    return db, products, transactions, reports


def test_inventory_report_tracks_stock_and_low_stock(tmp_path):
    _, products, transactions, reports = _services(tmp_path)
    product = products.add("پیچ فولادی", min_stock=5, category="تکنیکال", shelf="A-02")
    transactions.add(product.code, "IN", 8, "2026-10-01")
    transactions.add(product.code, "OUT", 4, "2026-10-02")

    rows = reports.inventory_rows()
    assert len(rows) == 1
    assert rows[0]["stock"] == 4
    assert rows[0]["shortage"] == 1
    assert rows[0]["status"] == "کم‌موجودی"
    assert rows[0]["last_movement"] == "2026-10-02"
    assert len(reports.inventory_rows(low_only=True)) == 1
    assert reports.inventory_rows(category="مصرفی") == []


def test_transaction_report_filters_date_and_product(tmp_path):
    _, products, transactions, reports = _services(tmp_path)
    first = products.add("بلبرینگ")
    second = products.add("تسمه")
    transactions.add(first.code, "IN", 10, "2026-10-01", "رسید خرید")
    transactions.add(second.code, "IN", 5, "2026-10-03")
    transactions.add(first.code, "OUT", 2, "2026-10-05", "مصرف")

    rows = reports.transaction_rows("2026-10-02", "2026-10-06", first.code)
    assert len(rows) == 1
    assert rows[0]["name"] == "بلبرینگ"
    assert rows[0]["type"] == "خروج"
    assert rows[0]["quantity"] == 2


def test_transaction_report_rejects_reversed_date_range(tmp_path):
    _, _, _, reports = _services(tmp_path)
    try:
        reports.transaction_rows("2026-10-10", "2026-10-01")
    except ValueError as exc:
        assert "تاریخ شروع" in str(exc)
    else:
        raise AssertionError("reversed date range should be rejected")


def test_csv_export_uses_excel_friendly_utf8_bom(tmp_path):
    _, products, _, reports = _services(tmp_path)
    products.add("مهره")
    path = reports.export_inventory_csv(tmp_path / "reports" / "inventory.csv")
    assert path.exists()
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "مهره" in path.read_text(encoding="utf-8-sig")
