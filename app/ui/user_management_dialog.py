# -*- coding: utf-8 -*-
"""مدیریت حساب‌های محلی و مشاهده رویدادهای حسابرسی (ویژه مدیر)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from app.services.user_service import AuthenticationError, UserService
from app.ui import theme as T


class UserManagementDialog(tk.Toplevel):
    """مدیر می‌تواند حساب بسازد، غیرفعال کند و رمز را بازنشانی کند."""

    def __init__(self, parent: tk.Misc, users: UserService, actor: str) -> None:
        super().__init__(parent)
        self.users = users
        self.actor = actor
        self.title("مدیریت کاربران و رویدادهای امنیتی")
        self.geometry("800x510")
        self.minsize(680, 420)
        self.configure(bg=T.BG)
        self.transient(parent)
        self._build()
        self.refresh()
        self.grab_set()

    def _build(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame", padding=(16, 12))
        header.pack(fill=tk.X)
        ttk.Label(header, text="مدیریت کاربران", style="Header.TLabel").pack(anchor="w")
        ttk.Label(header, text=f"مدیر فعال: {self.actor}", style="Header.Subtitle.TLabel").pack(anchor="w", pady=(3, 0))

        tabs = ttk.Notebook(self)
        tabs.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        users_tab = ttk.Frame(tabs, padding=10)
        audit_tab = ttk.Frame(tabs, padding=10)
        tabs.add(users_tab, text="حساب‌ها")
        tabs.add(audit_tab, text="گزارش رویدادها")

        columns = ("username", "display_name", "role", "active", "last_login")
        self.tree = ttk.Treeview(users_tab, columns=columns, show="headings", height=12)
        headers = {
            "username": ("نام کاربری", 130), "display_name": ("نام نمایشی", 150),
            "role": ("نقش", 100), "active": ("وضعیت", 90), "last_login": ("آخرین ورود", 210),
        }
        for key, (label, width) in headers.items():
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True)

        actions = ttk.Frame(users_tab)
        actions.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(actions, text="ایجاد کاربر", style="Primary.TButton", command=self._create_user).pack(side=tk.LEFT)
        ttk.Button(actions, text="فعال/غیرفعال‌سازی", command=self._toggle_active).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="بازنشانی رمز", command=self._reset_password).pack(side=tk.LEFT)
        ttk.Button(actions, text="تازه‌سازی", command=self.refresh).pack(side=tk.RIGHT)

        audit_columns = ("occurred_at", "username", "event", "details")
        self.audit = ttk.Treeview(audit_tab, columns=audit_columns, show="headings", height=14)
        for key, label, width in (
            ("occurred_at", "زمان (UTC)", 180), ("username", "کاربر", 110),
            ("event", "رویداد", 140), ("details", "جزئیات", 300),
        ):
            self.audit.heading(key, text=label)
            self.audit.column(key, width=width, anchor="w")
        self.audit.pack(fill=tk.BOTH, expand=True)
        ttk.Button(audit_tab, text="تازه‌سازی رویدادها", command=self._refresh_audit).pack(anchor="e", pady=(8, 0))

    def _selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("انتخاب کاربر", "ابتدا یک حساب را انتخاب کنید.", parent=self)
            return None
        return self.tree.item(selection[0], "values")

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for user in self.users.list_users():
            self.tree.insert("", tk.END, iid=str(user["id"]), values=(
                user["username"], user["display_name"],
                {"admin": "مدیر", "operator": "انباردار", "viewer": "مشاهده‌گر"}.get(user["role"], user["role"]),
                "فعال" if user["active"] else "غیرفعال",
                user["last_login_at"] or "—",
            ))
        self._refresh_audit()

    def _create_user(self) -> None:
        username = simpledialog.askstring("کاربر جدید", "نام کاربری (بدون فاصله):", parent=self)
        if not username:
            return
        display = simpledialog.askstring("کاربر جدید", "نام نمایشی:", parent=self)
        if not display:
            return
        role = simpledialog.askstring("نقش کاربر", "نقش را وارد کنید: operator یا viewer", initialvalue="operator", parent=self)
        if role not in ("operator", "viewer"):
            messagebox.showwarning("نقش نامعتبر", "برای امنیت، فقط operator یا viewer را می‌توان از این فرم ساخت.", parent=self)
            return
        password = simpledialog.askstring("رمز اولیه", "رمز عبور (حداقل ۱۰ نویسه، شامل حرف و عدد):", show="•", parent=self)
        if password is None:
            return
        try:
            self.users.create_user(username, display, password, role, self.actor)
            self.refresh()
            messagebox.showinfo("انجام شد", "حساب کاربری ساخته شد.", parent=self)
        except AuthenticationError as exc:
            messagebox.showerror("خطای اعتبارسنجی", str(exc), parent=self)

    def _toggle_active(self) -> None:
        values = self._selected()
        if values is None:
            return
        item_id = int(self.tree.selection()[0])
        is_active = values[3] == "فعال"
        if values[0] == self.actor and is_active:
            messagebox.showwarning("محدودیت", "نمی‌توانید حساب مدیر جاری را غیرفعال کنید.", parent=self)
            return
        if not messagebox.askyesno("تأیید", "وضعیت حساب تغییر کند؟", parent=self):
            return
        try:
            self.users.set_active(item_id, not is_active, self.actor)
            self.refresh()
        except AuthenticationError as exc:
            messagebox.showerror("عملیات ناموفق", str(exc), parent=self)

    def _reset_password(self) -> None:
        if self._selected() is None:
            return
        item_id = int(self.tree.selection()[0])
        password = simpledialog.askstring("بازنشانی رمز", "رمز جدید (حداقل ۱۰ نویسه، شامل حرف و عدد):", show="•", parent=self)
        if password is None:
            return
        try:
            self.users.reset_password(item_id, password, self.actor)
            self.refresh()
            messagebox.showinfo("انجام شد", "رمز عبور بازنشانی شد.", parent=self)
        except AuthenticationError as exc:
            messagebox.showerror("خطای اعتبارسنجی", str(exc), parent=self)

    def _refresh_audit(self) -> None:
        for item in self.audit.get_children():
            self.audit.delete(item)
        for event in self.users.recent_audit(250):
            self.audit.insert("", tk.END, values=(
                event["occurred_at"], event["username"], event["event"], event["details"]
            ))
