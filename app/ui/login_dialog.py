# -*- coding: utf-8 -*-
"""ورود و راه‌اندازی اولیه مدیر در اولین اجرای برنامه."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app.services.user_service import AuthenticationError, UserService
from app.ui import theme as T


class LoginDialog(tk.Toplevel):
    """فرم ورود؛ در اولین اجرا، فقط یک مدیر اولیه ایجاد می‌کند."""

    def __init__(self, parent: tk.Misc, users: UserService) -> None:
        super().__init__(parent)
        self.users = users
        self.user: dict | None = None
        self.title("ورود به EasyWarehouse")
        self.configure(bg=T.BG)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _event: self._cancel())
        self._build()
        self.update_idletasks()
        self._center()
        self.grab_set()
        self.after(100, self._focus_initial)

    def _build(self) -> None:
        card = ttk.Frame(self, padding=24, style="Metric.TFrame")
        card.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        brand = ttk.Frame(card, style="Header.TFrame", padding=(12, 10))
        brand.pack(fill=tk.X, pady=(0, 18))
        ttk.Label(brand, text="EasyWarehouse", style="Header.TLabel").pack(anchor="center", pady=(0, 4))
        ttk.Label(brand, text="مدیریت انبار امن و محلی", style="Header.Subtitle.TLabel").pack(anchor="center")

        self.setup_mode = not self.users.has_users()
        self.username_var = tk.StringVar()
        self.display_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.confirm_var = tk.StringVar()

        if self.setup_mode:
            ttk.Label(card, text="راه‌اندازی اولیه — ساخت مدیر", style="Section.TLabel").pack(anchor="e", pady=(0, 10))
            self._field(card, "نام نمایشی مدیر", self.display_var)
        else:
            ttk.Label(card, text="ورود به حساب کاربری", style="Section.TLabel").pack(anchor="e", pady=(0, 10))

        self.username_entry = self._field(card, "نام کاربری", self.username_var)
        self.password_entry = self._field(card, "رمز عبور", self.password_var, show="•")
        if self.setup_mode:
            self._field(card, "تکرار رمز عبور", self.confirm_var, show="•")

        ttk.Label(
            card,
            text="رمز باید حداقل ۱۰ نویسه و شامل حرف و عدد باشد.",
            style="Muted.TLabel",
        ).pack(anchor="e", pady=(8, 12))
        self.error_var = tk.StringVar()
        ttk.Label(card, textvariable=self.error_var, foreground=T.DANGER, wraplength=340).pack(fill=tk.X, pady=(0, 8))
        ttk.Button(
            card,
            text="ساخت مدیر و ورود" if self.setup_mode else "ورود",
            style="Primary.TButton",
            command=self._submit,
        ).pack(fill=tk.X, ipady=3)
        if not self.setup_mode:
            ttk.Button(card, text="خروج", style="Ghost.TButton", command=self._cancel).pack(fill=tk.X, pady=(8, 0))

    @staticmethod
    def _field(parent: ttk.Frame, label: str, variable: tk.StringVar, show: str | None = None):
        ttk.Label(parent, text=label).pack(anchor="e", pady=(5, 2))
        entry = ttk.Entry(parent, textvariable=variable, show=show, justify="left", width=38)
        entry.pack(fill=tk.X, ipady=4)
        return entry

    def _focus_initial(self) -> None:
        try:
            self.focus_force()
            self.username_entry.focus_set()
        except tk.TclError:
            pass

    def _center(self) -> None:
        width, height = 430, 470 if self.setup_mode else 410
        self.geometry(f"{width}x{height}")
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _submit(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get()
        try:
            if self.setup_mode:
                if password != self.confirm_var.get():
                    raise AuthenticationError("تکرار رمز عبور یکسان نیست.")
                self.users.setup_first_admin(username, self.display_var.get(), password)
            user = self.users.authenticate(username, password)
            if user is None:
                self.error_var.set("ورود ناموفق است؛ اطلاعات را بررسی کنید یا کمی بعد تلاش کنید.")
                self.password_var.set("")
                self.password_entry.focus_set()
                return
            self.user = user
            self.destroy()
        except AuthenticationError as exc:
            self.error_var.set(str(exc))
        except Exception as exc:
            self.error_var.set(f"خطا در ورود: {exc}")

    def _cancel(self) -> None:
        self.user = None
        self.destroy()
