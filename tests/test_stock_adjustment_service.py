from app.database.db_manager import DB
from app.services.product_service import ProductService
from app.services.stock_adjustment_service import StockAdjustmentService
from app.services.transaction_service import TransactionService
import pytest


def _setup(tmp_path):
    db = DB(tmp_path / "adjustments.db")
    products = ProductService(db)
    transactions = TransactionService(db)
    service = StockAdjustmentService(db)
    return db, products, transactions, service


def test_adjustment_creates_audited_incoming_transaction(tmp_path):
    db, products, transactions, service = _setup(tmp_path)
    product = products.add("پیچ")
    transactions.add(product.code, "IN", 8, "2026-10-01")
    result = service.create(product.code, 11, "شمارش پایان ماه", "operator",
                            expected_system_stock=8, reference="COUNT-001")
    assert result["variance"] == 3
    assert result["transaction_id"] is not None
    assert products.get(product.code).stock == 11
    assert service.all()[0]["reference"] == "COUNT-001"
    assert db.one("SELECT event FROM audit_log ORDER BY id DESC LIMIT 1")["event"] == "stock_adjustment_created"


def test_adjustment_reduces_stock_and_allows_zero_count(tmp_path):
    _, products, transactions, service = _setup(tmp_path)
    product = products.add("مهره")
    transactions.add(product.code, "IN", 8, "2026-10-01")
    result = service.create(product.code, 0, "کسری شمارش", "owner",
                            expected_system_stock=8, reference="COUNT-002")
    assert result["variance"] == -8
    assert products.get(product.code).stock == 0


def test_adjustment_rejects_duplicate_reference_and_stale_snapshot(tmp_path):
    _, products, transactions, service = _setup(tmp_path)
    product = products.add("واشر")
    transactions.add(product.code, "IN", 8, "2026-10-01")
    service.create(product.code, 8, "تطبیق", "owner",
                   expected_system_stock=8, reference="COUNT-003")
    with pytest.raises(ValueError, match="قبلاً ثبت"):
        service.create(product.code, 9, "تکراری", "owner",
                      expected_system_stock=8, reference="COUNT-003")
    transactions.add(product.code, "IN", 2, "2026-10-02")
    with pytest.raises(ValueError, match="تغییر کرده"):
        service.create(product.code, 9, "شمارش قدیمی", "owner",
                      expected_system_stock=8, reference="COUNT-004")


def test_adjustment_requires_reason_and_never_changes_stock_for_zero_variance(tmp_path):
    _, products, transactions, service = _setup(tmp_path)
    product = products.add("کابل")
    transactions.add(product.code, "IN", 4, "2026-10-01")
    with pytest.raises(ValueError, match="علت"):
        service.create(product.code, 4, " ", "owner",
                       expected_system_stock=4, reference="COUNT-005")
    result = service.create(product.code, 4, "تطبیق بدون اختلاف", "owner",
                            expected_system_stock=4, reference="COUNT-006")
    assert result["transaction_id"] is None
    assert products.get(product.code).stock == 4


def test_adjustment_movement_is_linked_to_a_warehouse_document(tmp_path):
    db, products, transactions, service = _setup(tmp_path)
    product = products.add("قطعه")
    result = service.create(product.code, 6, "شمارش", "operator",
                            expected_system_stock=0, reference="COUNT-DOC-01")
    assert result["document_id"] is not None
    assert result["document_no"]
    tx = db.one("SELECT document_id, document_no FROM transactions WHERE id=?",
                (result["transaction_id"],))
    assert tx["document_id"] == result["document_id"]
    assert tx["document_no"] == result["document_no"]
    doc = db.one("SELECT document_no, reference_no FROM warehouse_documents WHERE id=?",
                 (result["document_id"],))
    assert doc["document_no"] == result["document_no"]
    assert doc["reference_no"] == "COUNT-DOC-01"
