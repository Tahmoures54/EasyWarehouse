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


def test_kardex_running_balance_and_opening_balance(tmp_path):
    _, products, transactions, reports = _services(tmp_path)
    product = products.add("کابل برق")
    transactions.add(product.code, "IN", 20, "2026-10-01", "ورود اولیه")
    transactions.add(product.code, "OUT", 6, "2026-10-03", "مصرف")
    transactions.add(product.code, "RETURN", 2, "2026-10-04", "عودت")
    transactions.add(product.code, "OUT", 3, "2026-10-07", "مصرف دوم")

    rows = reports.kardex_rows(product.code, "2026-10-03", "2026-10-07")
    assert [r["type"] for r in rows] == [
        "مانده ابتدای دوره", "خروج", "عودت", "خروج"
    ]
    assert [r["balance"] for r in rows] == [20, 14, 16, 13]
    assert rows[1]["outgoing"] == 6
    assert rows[2]["incoming"] == 2


def test_kardex_accepts_user_code_and_exports_csv(tmp_path):
    _, products, transactions, reports = _services(tmp_path)
    product = products.add("فیلتر", user_code="FLT-1")
    transactions.add(product.code, "IN", 4, "2026-10-01")
    rows = reports.kardex_rows("FLT-1")
    assert rows[-1]["balance"] == 4
    assert rows[-1]["code"] == "FLT-1"
    assert rows[-1]["name"] == "فیلتر"
    assert rows[-1]["document_no"] == "EW-000001"
    path = reports.export_kardex_csv(tmp_path / "kardex.csv", "FLT-1")
    assert path.exists()
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    exported = path.read_text(encoding="utf-8-sig")
    assert "code,name" in exported.splitlines()[0]
    assert "FLT-1" in exported
    assert "فیلتر" in exported


def test_kardex_rejects_unknown_product_and_reversed_dates(tmp_path):
    _, _, _, reports = _services(tmp_path)
    try:
        reports.kardex_rows("MISSING")
    except ValueError as exc:
        assert "یافت نشد" in str(exc)
    else:
        raise AssertionError("unknown product should be rejected")

    product = _services(tmp_path)[1].add("واشر")
    try:
        reports.kardex_rows(product.code, "2026-10-10", "2026-10-01")
    except ValueError as exc:
        assert "تاریخ شروع" in str(exc)
    else:
        raise AssertionError("reversed date range should be rejected")


def test_kardex_csv_filters_movement_type_but_keeps_opening_balance(tmp_path):
    _, products, transactions, reports = _services(tmp_path)
    product = products.add("یاتاقان")
    transactions.add(product.code, "IN", 10, "2026-10-01", "ورود")
    transactions.add(product.code, "OUT", 3, "2026-10-02", "خروج")
    transactions.add(product.code, "RETURN", 1, "2026-10-03", "عودت")
    path = reports.export_kardex_csv(tmp_path / "out.csv", product.code, "2026-10-02", None, "خروج")
    rows = list(__import__("csv").DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    assert [row["type"] for row in rows] == ["مانده ابتدای دوره", "خروج"]
    assert rows[0]["balance"] == "10"
    assert rows[1]["balance"] == "7"


def test_stale_inventory_report_includes_only_positive_stock_older_than_threshold(tmp_path):
    _, products, transactions, reports = _services(tmp_path)
    stale = products.add("کالای راکد")
    recent = products.add("کالای تازه")
    empty = products.add("کالای ناموجود")
    never_moved = products.add("کالای بدون گردش")
    transactions.add(stale.code, "IN", 12, "2026-01-01")
    transactions.add(recent.code, "IN", 5, "2026-10-01")
    transactions.add(empty.code, "IN", 2, "2026-01-01")
    transactions.add(empty.code, "OUT", 2, "2026-01-02")
    rows = reports.stale_inventory_rows(days=90, as_of="2026-10-21")
    by_name = {row["name"]: row for row in rows}
    assert "کالای راکد" in by_name
    assert by_name["کالای راکد"]["days_since_movement"] == 293
    assert "کالای تازه" not in by_name
    assert "کالای ناموجود" not in by_name
    assert by_name["کالای بدون گردش"]["days_since_movement"] == "بدون گردش"


def test_inventory_count_template_is_read_only_and_csv_exported(tmp_path):
    _, products, transactions, reports = _services(tmp_path)
    product = products.add("کالای شمارش", min_stock=2)
    transactions.add(product.code, "IN", 7, "2026-10-01")
    path = reports.export_inventory_count_template_csv(tmp_path / "count.csv")
    rows = list(__import__("csv").DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    assert rows[0]["system_stock"] == "7.0"
    assert rows[0]["counted_stock"] == ""
    assert rows[0]["variance"] == ""
    assert products.get(product.code).stock == 7
