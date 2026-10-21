# -*- coding: utf-8 -*-
"""احراز هویت محلی، مدیریت حساب‌ها و ثبت رویدادهای امنیتی."""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from app.database.db_manager import DB, DatabaseError

_ROLES = {"admin", "operator", "viewer"}
_ITERATIONS = 310_000
_MIN_PASSWORD_LENGTH = 10
_MAX_FAILED_ATTEMPTS = 5
_LOCK_MINUTES = 15


class AuthenticationError(ValueError):
    """خطای قابل نمایش در فرایند ورود یا مدیریت حساب."""


class UserService:
    """حساب‌های محلی SQLite؛ رمزها با PBKDF2 و salt تصادفی ذخیره می‌شوند."""

    def __init__(self, db: DB) -> None:
        self.db = db
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.db.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    display_name TEXT NOT NULL,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','operator','viewer')),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    username TEXT NOT NULL DEFAULT '',
                    event TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(occurred_at DESC)"
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _password_material(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, _ITERATIONS, dklen=32
        )

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < _MIN_PASSWORD_LENGTH:
            raise AuthenticationError("رمز عبور باید حداقل ۱۰ نویسه داشته باشد.")
        if password.strip() != password or not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
            raise AuthenticationError("رمز عبور باید بدون فاصلهٔ ابتدا/انتها و شامل حرف و عدد باشد.")

    @staticmethod
    def _validate_username(username: str) -> str:
        username = username.strip()
        if not 3 <= len(username) <= 40:
            raise AuthenticationError("نام کاربری باید بین ۳ تا ۴۰ نویسه باشد.")
        if any(ch.isspace() for ch in username):
            raise AuthenticationError("نام کاربری نباید فاصله داشته باشد.")
        return username

    def has_users(self) -> bool:
        row = self.db.one("SELECT 1 FROM app_users LIMIT 1")
        return row is not None

    def setup_first_admin(self, username: str, display_name: str, password: str) -> None:
        username = self._validate_username(username)
        display_name = display_name.strip()
        if not display_name:
            raise AuthenticationError("نام نمایشی الزامی است.")
        self._validate_password(password)
        salt = os.urandom(16)
        hashed = self._password_material(password, salt)
        try:
            with self.db.transaction() as conn:
                if conn.execute("SELECT 1 FROM app_users LIMIT 1").fetchone():
                    raise AuthenticationError("مدیر اولیه قبلاً ساخته شده است.")
                conn.execute(
                    """INSERT INTO app_users
                       (username, display_name, password_salt, password_hash, role, created_at)
                       VALUES (?, ?, ?, ?, 'admin', ?)""",
                    (username, display_name, salt, hashed, self._now().isoformat()),
                )
                self._audit(conn, username, "first_admin_created", "حساب مدیر اولیه ساخته شد")
        except DatabaseError as exc:
            if "UNIQUE constraint failed: app_users.username" in str(exc):
                raise AuthenticationError("این نام کاربری قبلاً ثبت شده است.") from exc
            raise
        except sqlite3.IntegrityError as exc:
            raise AuthenticationError("این نام کاربری قبلاً ثبت شده است.") from exc

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        username = username.strip()
        row = self.db.one(
            """SELECT id, username, display_name, password_salt, password_hash,
                      role, active, failed_attempts, locked_until
               FROM app_users WHERE username = ?""",
            (username,),
        )
        if row is None:
            # هزینهٔ ثابت تقریبی برای نام‌های کاربری ناشناخته
            self._password_material(password, b"anbardari-asan-dummy-salt")
            self.log_event(username, "login_failed", "نام کاربری ناشناخته")
            return None
        now = self._now()
        if not row["active"]:
            self.log_event(row["username"], "login_denied", "حساب غیرفعال")
            return None
        if row["locked_until"]:
            try:
                locked_until = datetime.fromisoformat(row["locked_until"])
            except ValueError:
                locked_until = now
            if locked_until > now:
                self.log_event(row["username"], "login_denied", "حساب موقتاً قفل است")
                return None
        actual = self._password_material(password, bytes(row["password_salt"]))
        if not hmac.compare_digest(actual, bytes(row["password_hash"])):
            failed = int(row["failed_attempts"]) + 1
            locked = (now.replace(microsecond=0) + timedelta(minutes=_LOCK_MINUTES)).isoformat() if failed >= _MAX_FAILED_ATTEMPTS else None
            self.db.execute(
                "UPDATE app_users SET failed_attempts=?, locked_until=? WHERE id=?",
                (failed, locked, row["id"]),
            )
            self.log_event(row["username"], "login_failed", f"تلاش ناموفق شماره {failed}")
            return None
        self.db.execute(
            "UPDATE app_users SET failed_attempts=0, locked_until=NULL, last_login_at=? WHERE id=?",
            (now.isoformat(), row["id"]),
        )
        self.log_event(row["username"], "login_success", "ورود موفق")
        return {
            "id": int(row["id"]), "username": row["username"],
            "display_name": row["display_name"], "role": row["role"],
        }

    def list_users(self) -> list[dict[str, Any]]:
        rows = self.db.all(
            """SELECT id, username, display_name, role, active, created_at, last_login_at
               FROM app_users ORDER BY username"""
        )
        return [dict(row) for row in rows]

    def create_user(self, username: str, display_name: str, password: str, role: str, actor: str) -> None:
        username = self._validate_username(username)
        display_name = display_name.strip()
        if not display_name:
            raise AuthenticationError("نام نمایشی الزامی است.")
        if role not in _ROLES:
            raise AuthenticationError("نقش انتخاب‌شده معتبر نیست.")
        self._validate_password(password)
        salt = os.urandom(16)
        try:
            with self.db.transaction() as conn:
                conn.execute(
                    """INSERT INTO app_users
                       (username, display_name, password_salt, password_hash, role, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (username, display_name, salt, self._password_material(password, salt),
                     role, self._now().isoformat()),
                )
                self._audit(conn, actor, "user_created", f"کاربر {username} با نقش {role} ساخته شد")
        except DatabaseError as exc:
            if "UNIQUE constraint failed: app_users.username" in str(exc):
                raise AuthenticationError("این نام کاربری قبلاً ثبت شده است.") from exc
            raise
        except sqlite3.IntegrityError as exc:
            raise AuthenticationError("این نام کاربری قبلاً ثبت شده است.") from exc

    def set_role(self, user_id: int, role: str, actor: str) -> None:
        if role not in _ROLES:
            raise AuthenticationError("نقش انتخاب‌شده معتبر نیست.")
        with self.db.transaction() as conn:
            target = conn.execute(
                "SELECT username, role, active FROM app_users WHERE id=?", (user_id,)
            ).fetchone()
            if target is None:
                raise AuthenticationError("کاربر پیدا نشد.")
            if target["role"] == "admin" and target["active"] and role != "admin":
                admins = conn.execute(
                    "SELECT COUNT(*) FROM app_users WHERE role='admin' AND active=1"
                ).fetchone()[0]
                if admins <= 1:
                    raise AuthenticationError("تغییر نقش آخرین مدیر فعال مجاز نیست.")
            conn.execute("UPDATE app_users SET role=? WHERE id=?", (role, user_id))
            self._audit(conn, actor, "user_role_changed", f"{target['username']}: {target['role']} -> {role}")

    def set_active(self, user_id: int, active: bool, actor: str) -> None:
        with self.db.transaction() as conn:
            target = conn.execute(
                "SELECT username, role, active FROM app_users WHERE id=?", (user_id,)
            ).fetchone()
            if target is None:
                raise AuthenticationError("کاربر پیدا نشد.")
            if not active and target["role"] == "admin" and target["active"]:
                admins = conn.execute(
                    "SELECT COUNT(*) FROM app_users WHERE role='admin' AND active=1"
                ).fetchone()[0]
                if admins <= 1:
                    raise AuthenticationError("غیرفعال‌کردن آخرین مدیر فعال مجاز نیست.")
            conn.execute("UPDATE app_users SET active=?, failed_attempts=0, locked_until=NULL WHERE id=?", (int(active), user_id))
            self._audit(conn, actor, "user_activated" if active else "user_deactivated", target["username"])

    def reset_password(self, user_id: int, password: str, actor: str) -> None:
        self._validate_password(password)
        salt = os.urandom(16)
        with self.db.transaction() as conn:
            row = conn.execute("SELECT username FROM app_users WHERE id=?", (user_id,)).fetchone()
            if row is None:
                raise AuthenticationError("کاربر پیدا نشد.")
            conn.execute(
                "UPDATE app_users SET password_salt=?, password_hash=?, failed_attempts=0, locked_until=NULL WHERE id=?",
                (salt, self._password_material(password, salt), user_id),
            )
            self._audit(conn, actor, "password_reset", f"رمز کاربر {row['username']} بازنشانی شد")

    def log_event(self, username: str, event: str, details: str = "") -> None:
        try:
            with self.db.transaction() as conn:
                self._audit(conn, username, event, details[:500])
        except Exception:
            # رخدادهای ممیزی نباید برنامهٔ اصلی را از کار بیندازند؛ خطا در لاگ ثبت می‌شود.
            import logging
            logging.getLogger(__name__).exception("Failed to write audit event")

    @staticmethod
    def _audit(conn, username: str, event: str, details: str) -> None:
        conn.execute(
            "INSERT INTO audit_log(occurred_at, username, event, details) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), username[:80], event[:80], details[:500]),
        )

    def recent_audit(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        rows = self.db.all(
            "SELECT occurred_at, username, event, details FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in rows]
