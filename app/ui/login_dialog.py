# -*- coding: utf-8 -*-
"""ورود و راه‌اندازی اولیه مدیر در اولین اجرای برنامه."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from app.config import APP_BRAND
from app.services.user_service import AuthenticationError, UserService
from app.ui import theme as T

logger = logging.getLogger(__name__)

# --- ثابت‌های ظاهری/رفتاری (به‌جای اعداد جادویی) ---------------------------
_PREFERRED_WIDTH = 430       # حداقل عرض مطلوب؛ ارتفاع به‌صورت پویا محاسبه می‌شود
_ERROR_WRAP = 340            # عرض شکستن خط پیام خطا (هماهنگ با عرض کارت)
_MIN_PASSWORD_LENGTH = 10    # حداقل طول رمز در حالت راه‌اندازی اولیه
_FOCUS_DELAY_MS = 150        # تأخیر کوتاه پس از map شدن پنجره برای focus_force


class LoginDialog(tk.Toplevel):
    """فرم ورود؛ در اولین اجرا، فقط یک مدیر اولیه ایجاد می‌کند."""

    def __init__(self, parent: tk.Misc, users: UserService) -> None:
        super().__init__(parent)
        self.users = users
        self.user: dict | None = None
        self.title(f"ورود به {APP_BRAND}")
        self.configure(bg=T.BG)
        self.resizable(False, False)

        # A transient child of a withdrawn root can remain hidden on Windows.
        # Only establish transient ownership when the parent is actually visible.
        try:
            if parent.winfo_viewable():
                self.transient(parent)
        except tk.TclError:
            pass

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _event: self._cancel())

        self._build()
        self._center()

        # Explicitly map and raise the dialog before taking the modal grab.
        # The parent MainWindow is intentionally withdrawn during authentication.
        self.deiconify()
        self.lift()
        try:
            # Grabbing an unmapped window raises TclError on some platforms
            # (notably Windows). Wait for the Map event first.
            self.wait_visibility()
        except tk.TclError:
            pass
        try:
            self.grab_set()
        except tk.TclError:
            # Another modal may already hold the grab; keep the dialog usable.
            logger.debug("Unable to set modal grab on login dialog", exc_info=True)

        self.after(_FOCUS_DELAY_MS, self._focus_initial)

    # ------------------------------------------------------------------ UI --
    def _build(self) -> None:
        card = ttk.Frame(self, padding=24, style="Metric.TFrame")
        card.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        brand = ttk.Frame(card, style="Header.TFrame", padding=(12, 10))
        brand.pack(fill=tk.X, pady=(0, 18))
        ttk.Label(brand, text=APP_BRAND, style="Header.TLabel").pack(anchor="center", pady=(0, 4))
        ttk.Label(brand, text="مدیریت انبار امن و محلی", style="Header.Subtitle.TLabel").pack(anchor="center")

        self.setup_mode = not self.users.has_users()

        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()

        # فیلدهای نمایشی/تکرار رمز فقط در حالت راه‌اندازی معنا دارند.
        self.display_var: tk.StringVar | None = None
        self.confirm_var: tk.StringVar | None = None
        self.display_entry: ttk.Entry | None = None
        self.confirm_entry: ttk.Entry | None = None

        if self.setup_mode:
            self.display_var = tk.StringVar()
            self.confirm_var = tk.StringVar()
            ttk.Label(card, text="راه‌اندازی اولیه — ساخت مدیر", style="Section.TLabel").pack(anchor="e", pady=(0, 10))
            assert self.display_var is not None
            self.display_entry = self._field(card, "نام نمایشی مدیر", self.display_var)
        else:
            ttk.Label(card, text="ورود به حساب کاربری", style="Section.TLabel").pack(anchor="e", pady=(0, 10))

        self.username_entry = self._field(card, "نام کاربری", self.username_var)
        self.password_entry = self._field(card, "رمز عبور", self.password_var, show="•")

        if self.setup_mode:
            assert self.confirm_var is not None
            self.confirm_entry = self._field(card, "تکرار رمز عبور", self.confirm_var, show="•")

        ttk.Label(
            card,
            text=f"رمز باید حداقل {_MIN_PASSWORD_LENGTH} نویسه و شامل حرف و عدد باشد.",
            style="Muted.TLabel",
        ).pack(anchor="e", pady=(8, 12))

        self.error_var = tk.StringVar()
        # theme فعلی استایل Danger.TLabel ندارد؛ برای سازگاری با تم‌های مختلف
        # از override مستقیم foreground استفاده می‌کنیم.
        ttk.Label(
            card,
            textvariable=self.error_var,
            foreground=T.DANGER,
            wraplength=_ERROR_WRAP,
        ).pack(fill=tk.X, pady=(0, 8))

        ttk.Button(
            card,
            text="ساخت مدیر و ورود" if self.setup_mode else "ورود",
            style="Primary.TButton",
            command=self._submit,
        ).pack(fill=tk.X, ipady=3)

        if not self.setup_mode:
            ttk.Button(
                card, text="خروج", style="Ghost.TButton", command=self._cancel
            ).pack(fill=tk.X, pady=(8, 0))

    def _field(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        show: str | None = None,
    ) -> ttk.Entry:
        ttk.Label(parent, text=label).pack(anchor="e", pady=(5, 2))
        entry = ttk.Entry(parent, textvariable=variable, show=show, justify="left", width=38)
        entry.pack(fill=tk.X, ipady=4)
        # Enter فقط روی فیلدهای متنی بایند می‌شود تا در صورت فوکوس روی دکمه،
        # هم invoke دکمه و هم _submit به‌صورت دوگانه اجرا نشوند.
        entry.bind("<Return>", lambda _event: self._submit())
        return entry

    # -------------------------------------------------------------- layout --
    def _center(self) -> None:
        self.update_idletasks()
        width = max(self.winfo_reqwidth(), _PREFERRED_WIDTH)
        height = self.winfo_reqheight()
        x = max((self.winfo_screenwidth() - width) // 2, 0)
        y = max((self.winfo_screenheight() - height) // 2, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _focus_initial(self) -> None:
        try:
            self.focus_force()
            self.username_entry.focus_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------- helpers --
    def _show_error(self, message: str, entry: ttk.Entry | None = None) -> None:
        self.error_var.set(message)
        if entry is not None:
            try:
                entry.focus_set()
            except tk.TclError:
                pass

    # -------------------------------------------------------------- submit --
    def _submit(self) -> None:
        self.error_var.set("")
        username = self.username_var.get().strip()
        password = self.password_var.get()

        # اعتبارسنجی محلی پیش از فراخوانی سرویس (بازخورد فوری‌تر).
        if not username:
            self._show_error("نام کاربری را وارد کنید.", self.username_entry)
            return
        if not password:
            self._show_error("رمز عبور را وارد کنید.", self.password_entry)
            return

        display_name = ""
        if self.setup_mode:
            assert self.display_var is not None and self.confirm_var is not None
            display_name = self.display_var.get().strip()
            if not display_name:
                self._show_error("نام نمایشی مدیر را وارد کنید.", self.display_entry)
                return
            if password != self.confirm_var.get():
                self._show_error("تکرار رمز عبور یکسان نیست.", self.confirm_entry)
                return
            if len(password) < _MIN_PASSWORD_LENGTH:
                self._show_error(
                    f"رمز باید حداقل {_MIN_PASSWORD_LENGTH} نویسه باشد.",
                    self.password_entry,
                )
                return
            if not (any(ch.isalpha() for ch in password) and any(ch.isdigit() for ch in password)):
                self._show_error("رمز باید شامل حرف و عدد باشد.", self.password_entry)
                return

        setup_completed = False
        try:
            if self.setup_mode:
                created = self.users.setup_first_admin(username, display_name, password)
                setup_completed = True
                # اگر سرویس، کاربر ساخته‌شده را برگرداند از آن استفاده می‌کنیم؛
                # در غیر این صورت یک بار authenticate می‌زنیم.
                self.user = (
                    created if isinstance(created, dict)
                    else self.users.authenticate(username, password)
                )
            else:
                self.user = self.users.authenticate(username, password)
        except AuthenticationError as exc:
            self._show_error(str(exc), self.password_entry)
            self.password_var.set("")
            return
        except Exception:
            # جزئیات استثنا فقط در لاگ می‌ماند و به کاربر نمایش داده نمی‌شود.
            logger.exception("Unexpected error during authentication")
            self._show_error("خطای غیرمنتظره در ورود رخ داد. لطفاً دوباره تلاش کنید.")
            return

        if self.user is None:
            if setup_completed:
                # مدیر ساخته شد اما ورود خودکار ناموفق بود (مثلاً rate-limit).
                # حالت را به ورود عادی تغییر می‌دهیم تا تلاش مجدد، دوباره
                # سعی در ساخت مدیر نکند.
                self.setup_mode = False
                self._show_error(
                    "مدیر ساخته شد اما ورود خودکار ناموفق بود؛ لطفاً دوباره وارد شوید.",
                    self.password_entry,
                )
            else:
                self._show_error(
                    "ورود ناموفق است؛ اطلاعات را بررسی کنید یا کمی بعد تلاش کنید.",
                    self.password_entry,
                )
            self.password_var.set("")
            return

        self.destroy()

    def _cancel(self) -> None:
        self.user = None
        self.destroy()
