# -*- coding: utf-8 -*-
"""آزمون‌های حساب کاربری محلی و ثبت رویدادهای امنیتی."""

import sqlite3

import pytest

from app.database.db_manager import DB
from app.services.user_service import AuthenticationError, UserService


@pytest.fixture
def users(tmp_path):
    db = DB(tmp_path / "users-test.db")
    return UserService(db)


def test_first_admin_and_password_are_hashed(users, tmp_path):
    users.setup_first_admin("owner", "مدیر سیستم", "SecurePass123")
    assert users.has_users()
    user = users.authenticate("owner", "SecurePass123")
    assert user["role"] == "admin"
    assert user["display_name"] == "مدیر سیستم"
    raw = users.db.one("SELECT password_hash, password_salt FROM app_users WHERE username='owner'")
    assert bytes(raw["password_hash"]) != b"SecurePass123"
    assert bytes(raw["password_salt"]) != b""


def test_first_admin_cannot_be_created_twice(users):
    users.setup_first_admin("owner", "مدیر", "SecurePass123")
    with pytest.raises(AuthenticationError):
        users.setup_first_admin("other", "دیگری", "SecurePass123")


def test_invalid_password_policy_is_enforced(users):
    with pytest.raises(AuthenticationError):
        users.setup_first_admin("owner", "مدیر", "short")
    with pytest.raises(AuthenticationError):
        users.setup_first_admin("owner", "مدیر", "onlyletterslong")


def test_login_failures_are_audited_and_account_locks(users):
    users.setup_first_admin("owner", "مدیر", "SecurePass123")
    for _ in range(5):
        assert users.authenticate("owner", "WrongPass123") is None
    assert users.authenticate("owner", "SecurePass123") is None
    assert any(row["event"] == "login_failed" for row in users.recent_audit())


def test_roles_activation_and_last_admin_guard(users):
    users.setup_first_admin("owner", "مدیر", "SecurePass123")
    users.create_user("viewer1", "مشاهده‌گر", "ViewerPass123", "viewer", "owner")
    viewer = next(row for row in users.list_users() if row["username"] == "viewer1")
    users.set_active(viewer["id"], False, "owner")
    assert not next(row for row in users.list_users() if row["username"] == "viewer1")["active"]
    admin = next(row for row in users.list_users() if row["username"] == "owner")
    with pytest.raises(AuthenticationError):
        users.set_active(admin["id"], False, "owner")


def test_duplicate_username_is_rejected_case_insensitively(users):
    users.setup_first_admin("owner", "مدیر", "SecurePass123")
    with pytest.raises(AuthenticationError):
        users.create_user("OWNER", "تکراری", "OtherPass123", "viewer", "owner")


def test_audit_log_is_written(users):
    users.setup_first_admin("owner", "مدیر", "SecurePass123")
    users.authenticate("owner", "SecurePass123")
    events = [row["event"] for row in users.recent_audit()]
    assert "first_admin_created" in events
    assert "login_success" in events
