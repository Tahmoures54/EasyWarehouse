# -*- coding: utf-8 -*-
"""مدیریت حساب‌های محلی و مشاهده رویدادهای حسابرسی (ویژه مدیر)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from app.services.user_service import AuthenticationError, UserService
from app.ui import theme as T

logger = logging.getLogger(__name__)

# --- ثابت‌ها ---------------------------------------------------------------
_WINDOW_SIZE = (800, 510)
_MIN_SIZE = (680, 420)
_AUDIT_LIMIT = 250
_MIN_PASSWORD_LENGTH = 10
_FOCUS_DELAY_MS = 150

ROLE_LABELS: dict[str, str] = {
    "admin": "مدیر",
    "operator": "انباردار",
    "viewer": "مشاهده‌گر",
}
ROLES: tuple[str, ...] = tuple(ROLE_LABELS.keys())


def _validate_password(password: str) -> str | None:
    """پیام خطای فارسی برمی‌گرداند یا None اگر معتبر بود."""
    if len(password) < _MIN_PASSWORD_LENGTH:
        return f"رمز باید حداقل {_MIN_PASSWORD_LENGTH} نویسه باشد."
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        return "رمز باید شامل حرف و عدد باشد."
    return None


class _RolePicker(tk.Toplevel):
    """انتخاب نقش از میان نقش‌های مجاز با Combobox (به‌جای تایپ دستی)."""

    def __init__(self, parent: tk.Misc, title: str, initial: str = "operator") -> None:
        super().__init__(parent)
        self.result: str | None = None
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=T.BG)
        try:
            if parent.winfo_viewable():
                self.transient(parent)
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

        body = ttk.Frame(self, padding=16, style="Metric.TFrame")
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, text="نقش کاربر:").pack(anchor="e", pady=(0, 6))

        labels = list(ROLE_LABELS.values())
        default_label = ROLE_LABELS.get(initial, labels[0])
        self._label_var = tk.StringVar(value=default_label)
        combo = ttk.Combobox(
            body, textvariable=self._label_var, values=labels,
            state="readonly", width=24, justify="right",
        )
        combo.pack(fill=tk.X)

        buttons = ttk.Frame(body)
        buttons.pack(fill=tk.X, pady=(14, 0))
        ttk.Button(buttons, text="تأیید", style="Primary.TButton",
                   command=self._accept).pack(side=tk.LEFT)
        ttk.Button(buttons, text="انصراف", style="Ghost.TButton",
                   command=self._cancel).pack(side=tk.RIGHT)

        self.update_idletasks()
        self._center(parent)
        self.deiconify()
        self.lift()
        try:
            self.wait_visibility()
        except tk.TclError:
            pass
        try:
            self.grab_set()
        except tk.TclError:
            logger.debug("Role picker grab failed", exc_info=True)
        self.after(_FOCUS_DELAY_MS, self._focus)

    def _focus(self) -> None:
        try:
            self.focus_force()
        except tk.TclError:
            pass

    def _center(self, parent: tk.Misc) -> None:
        width = max(self.winfo_reqwidth(), 320)
        height = self.winfo_reqheight()
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        except tk.TclError:
            x = (self.winfo_screenwidth() - width) // 2
            y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")

    def _accept(self) -> None:
        label = self._label_var.get()
        for value, text in ROLE_LABELS.items():
            if text == label:
                self.result = value
                self.destroy()
                return
        self._cancel()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    @classmethod
    def ask(cls, parent: tk.Misc, title: str, initial: str = "operator") -> str | None:
        dialog = cls(parent, title, initial)
        parent.wait_window(dialog)
        return dialog.result


class UserManagementDialog(tk.Toplevel):
    """مدیر می‌تواند حساب بسازد، غیرفعال کند و رمز را بازنشانی کند."""

    def __init__(self, parent: tk.Misc, users: UserService, actor: str) -> None:
        super().__init__(parent)
        self.users = users
        self.actor = actor
        self.title("مدیریت کاربران و رویدادهای امنیتی")
        self.minsize(*_MIN_SIZE)
        self.configure(bg=T.BG)

        # A transient child of a withdrawn root can remain hidden on Windows.
        try:
            if parent.winfo_viewable():
                self.transient(parent)
        except tk.TclError:
            pass

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _e: self._close())

        # نگهداری دادهٔ خام کاربران برای دسترسی امن (بدون تطبیق رشته‌ای).
        self._rows: dict[int, dict] = {}

        self._build()
        self.refresh()
        self._refresh_audit()

        self.update_idletasks()
        self._center()
        self.deiconify()
        self.lift()
        try:
            # Grabbing an unmapped window raises TclError on some platforms.
            self.wait_visibility()
        except tk.TclError:
            pass
        try:
            self.grab_set()
        except tk.TclError:
            logger.debug("User management grab failed", exc_info=True)

    # ------------------------------------------------------------- helpers --
    def _close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def _regrab(self) -> None:
        """پس از بستن یک زیردیالوگ مودال، مودال بودن این پنجره را بازیابی می‌کند."""
        try:
            if self.winfo_exists():
                self.grab_set()
        except tk.TclError:
            logger.debug("Regrab failed", exc_info=True)

    def _center(self) -> None:
        width = max(_WINDOW_SIZE[0], self.winfo_reqwidth())
        height = max(_WINDOW_SIZE[1], self.winfo_reqheight())
        x = max((self.winfo_screenwidth() - width) // 2, 0)
        y = max((self.winfo_screenheight() - height) // 2, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _ask_string(self, title: str, prompt: str) -> str | None:
        try:
            return simpledialog.askstring(title, prompt, parent=self)
        finally:
            self._regrab()

    def _ask_password(self, title: str, prompt: str) -> str | None:
        try:
            while True:
                password = simpledialog.askstring(title, prompt, show="•", parent=self)
                self._regrab()  # میان حلقه هم مودال بودن را حفظ می‌کنیم
                if not password:
                    return None
                error = _validate_password(password)
                if error:
                    messagebox.showerror("رمز نامعتبر", error, parent=self)
                    continue
                return password
        finally:
            self._regrab()

    def _ask_role(self, title: str, initial: str = "operator") -> str | None:
        try:
            return _RolePicker.ask(self, title, initial)
        finally:
            self._regrab()

    # ------------------------------------------------------------------ UI --
    def _build(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame", padding=(16, 12))
        header.pack(fill=tk.X)
        ttk.Label(header, text="مدیریت کاربران",
                  style="Header.TLabel").pack(anchor="w")
        ttk.Label(header, text=f"مدیر فعال: {self.actor}",
                  style="Header.Subtitle.TLabel").pack(anchor="w", pady=(3, 0))

        self._tabs = ttk.Notebook(self)
        self._tabs.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        users_tab = ttk.Frame(self._tabs, padding=10)
        audit_tab = ttk.Frame(self._tabs, padding=10)
        self._tabs.add(users_tab, text="حساب‌ها")
        self._tabs.add(audit_tab, text="گزارش رویدادها")
        self._tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # --- تب حساب‌ها
        columns = ("username", "display_name", "role", "active", "last_login")
        self.tree = ttk.Treeview(users_tab, columns=columns, show="headings", height=12)
        headers = {
            "username": ("نام کاربری", 130),
            "display_name": ("نام نمایشی", 150),
            "role": ("نقش", 100),
            "active": ("وضعیت", 90),
            "last_login": ("آخرین ورود", 210),
        }
        for key, (label, width) in headers.items():
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True)

        actions = ttk.Frame(users_tab)
        actions.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(actions, text="ایجاد کاربر", style="Primary.TButton",
                   command=self._create_user).pack(side=tk.LEFT)
        ttk.Button(actions, text="فعال/غیرفعال‌سازی",
                   command=self._toggle_active).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="تغییر نقش",
                   command=self._change_role).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="بازنشانی رمز",
                   command=self._reset_password).pack(side=tk.LEFT)
        ttk.Button(actions, text="تازه‌سازی",
                   command=self.refresh).pack(side=tk.RIGHT)

        # --- تب رویدادها
        audit_columns = ("occurred_at", "username", "event", "details")
        self.audit = ttk.Treeview(audit_tab, columns=audit_columns,
                                 show="headings", height=14)
        for key, label, width in (
            ("occurred_at", "زمان (UTC)", 180),
            ("username", "کاربر", 110),
            ("event", "رویداد", 140),
            ("details", "جزئیات", 300),
        ):
            self.audit.heading(key, text=label)
            self.audit.column(key, width=width, anchor="w")
        self.audit.pack(fill=tk.BOTH, expand=True)
        ttk.Button(audit_tab, text="تازه‌سازی رویدادها",
                   command=self._refresh_audit).pack(anchor="e", pady=(8, 0))

    def _on_tab_changed(self, _event: tk.Event) -> None:
        try:
            if self._tabs.index(self._tabs.select()) == 1:
                self._refresh_audit()
        except (tk.TclError, IndexError):
            pass

    # ---------------------------------------------------------- selection --
    def _selected(self) -> tuple[int, dict] | None:
        """(شناسه، دادهٔ خام کاربر) برمی‌گرداند یا None با پیام به کاربر."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("انتخاب کاربر",
                                "ابتدا یک حساب را انتخاب کنید.", parent=self)
            return None
        try:
            item_id = int(selection[0])
        except (TypeError, ValueError):
            return None
        user = self._rows.get(item_id)
        if user is None:
            return None
        return item_id, user

    # -------------------------------------------------------------- refresh --
    def refresh(self) -> None:
        try:
            users = list(self.users.list_users())
        except Exception:
            logger.exception("list_users failed")
            messagebox.showerror("خطا",
                                 "دریافت فهرست کاربران ناموفق بود.", parent=self)
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows.clear()
        for user in users:
            iid = int(user["id"])
            self._rows[iid] = user
            self.tree.insert("", tk.END, iid=str(iid), values=(
                user["username"],
                user["display_name"],
                ROLE_LABELS.get(user["role"], user["role"]),
                "فعال" if user["active"] else "غیرفعال",
                user["last_login_at"] or "—",
            ))

    def _refresh_audit(self) -> None:
        try:
            events = list(self.users.recent_audit(_AUDIT_LIMIT))
        except Exception:
            logger.exception("recent_audit failed")
            return
        for item in self.audit.get_children():
            self.audit.delete(item)
        for event in events:
            self.audit.insert("", tk.END, values=(
                event["occurred_at"], event["username"],
                event["event"], event["details"],
            ))

    # -------------------------------------------------------------- actions --
    def _create_user(self) -> None:
        username = self._ask_string("کاربر جدید", "نام کاربری (بدون فاصله):")
        if not username or not username.strip():
            return
        username = username.strip()
        if " " in username:
            messagebox.showwarning("نام کاربری نامعتبر",
                                   "نام کاربری نباید شامل فاصله باشد.", parent=self)
            return

        display = self._ask_string("کاربر جدید", "نام نمایشی:")
        if not display or not display.strip():
            return
        display = display.strip()

        role = self._ask_role("نقش کاربر جدید", initial="operator")
        if role is None or role not in ROLES:
            return

        password = self._ask_password(
            "رمز اولیه",
            f"رمز عبور (حداقل {_MIN_PASSWORD_LENGTH} نویسه، شامل حرف و عدد):",
        )
        if password is None:
            return

        try:
            self.users.create_user(username, display, password, role, self.actor)
        except AuthenticationError as exc:
            messagebox.showerror("خطای اعتبارسنجی", str(exc), parent=self)
            return
        except Exception:
            logger.exception("create_user failed")
            messagebox.showerror("خطای غیرمنتظره",
                                 "ساخت کاربر ناموفق بود. لطفاً دوباره تلاش کنید.",
                                 parent=self)
            return
        self.refresh()
        messagebox.showinfo("انجام شد", "حساب کاربری ساخته شد.", parent=self)

    def _toggle_active(self) -> None:
        selection = self._selected()
        if selection is None:
            return
        item_id, user = selection
        is_active = bool(user["active"])
        if user["username"] == self.actor and is_active:
            messagebox.showwarning(
                "محدودیت",
                "نمی‌توانید حساب مدیر جاری را غیرفعال کنید.",
                parent=self,
            )
            return
        action = "غیرفعال" if is_active else "فعال"
        if not messagebox.askyesno(
            "تأیید",
            f"حساب «{user['username']}» {action} شود؟",
            parent=self,
        ):
            return
        try:
            self.users.set_active(item_id, not is_active, self.actor)
        except AuthenticationError as exc:
            messagebox.showerror("عملیات ناموفق", str(exc), parent=self)
            return
        except Exception:
            logger.exception("set_active failed")
            messagebox.showerror("خطای غیرمنتظره",
                                 "تغییر وضعیت ناموفق بود.", parent=self)
            return
        self.refresh()

    def _change_role(self) -> None:
        selection = self._selected()
        if selection is None:
            return
        item_id, user = selection
        if user["username"] == self.actor:
            messagebox.showwarning(
                "محدودیت",
                "تغییر نقش حساب مدیر جاری از داخل همان نشست مجاز نیست.",
                parent=self,
            )
            return
        role = self._ask_role("تغییر نقش", initial=user["role"])
        if role is None or role not in ROLES:
            return
        if role == user["role"]:
            return
        try:
            self.users.set_role(item_id, role, self.actor)
        except AuthenticationError as exc:
            messagebox.showerror("عملیات ناموفق", str(exc), parent=self)
            return
        except Exception:
            logger.exception("set_role failed")
            messagebox.showerror("خطای غیرمنتظره",
                                 "تغییر نقش ناموفق بود.", parent=self)
            return
        self.refresh()

    def _reset_password(self) -> None:
        selection = self._selected()
        if selection is None:
            return
        item_id, user = selection
        if not messagebox.askyesno(
            "تأیید بازنشانی",
            f"رمز حساب «{user['username']}» بازنشانی شود؟",
            parent=self,
        ):
            return
        password = self._ask_password(
            "بازنشانی رمز",
            f"رمز جدید (حداقل {_MIN_PASSWORD_LENGTH} نویسه، شامل حرف و عدد):",
        )
        if password is None:
            return
        try:
            self.users.reset_password(item_id, password, self.actor)
        except AuthenticationError as exc:
            messagebox.showerror("خطای اعتبارسنجی", str(exc), parent=self)
            return
        except Exception:
            logger.exception("reset_password failed")
            messagebox.showerror("خطای غیرمنتظره",
                                 "بازنشانی رمز ناموفق بود.", parent=self)
            return
        self.refresh()
        messagebox.showinfo("انجام شد", "رمز عبور بازنشانی شد.", parent=self)
