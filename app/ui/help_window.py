# -*- coding: utf-8 -*-
"""پنجره راهنمای کاربر (F1)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Iterable

from app.config import APP_NAME
from app.ui import theme as T

logger = logging.getLogger(__name__)

# --- ثابت‌های ظاهری/رفتاری ------------------------------------------------
DEFAULT_WIDTH = 800
DEFAULT_HEIGHT = 600
MIN_WIDTH = 640
MIN_HEIGHT = 480
_EDGE_MARGIN = 20       # فاصلهٔ امن از لبه‌های صفحه (taskbar/dock)
_STATUS_CLEAR_MS = 3000  # پاک شدن پیام موقت کپی


class HelpWindow(tk.Toplevel):
    """راهنمای غیرمودال با ۴ تب فارسی."""

    # عنوان‌های تب‌ها به‌عنوان منبع حقیقت واحد (جلوگیری از تکرار در _copy_all).
    _TAB_TITLES: tuple[str, ...] = (
        "شروع سریع",
        "ثبت تراکنش",
        "مدیریت کالاها",
        "سوالات متداول",
    )

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self._texts: list[tk.Text] = []
        self._status_var = tk.StringVar(value="")
        self._status_after_id: str | None = None
        self._configure_window(master)
        self._build()
        self._bind_shortcuts()
        self._center_on(master)

    # -------------------------------------------------------------- setup --
    def _configure_window(self, master: tk.Misc | None) -> None:
        self.title(f"راهنمای کاربر — {APP_NAME}")
        self.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.configure(bg=T.BG)
        self.protocol("WM_DELETE_WINDOW", self._close)
        # A transient child of a withdrawn root can remain hidden on Windows.
        if master is not None:
            try:
                if master.winfo_viewable():
                    self.transient(master)
            except tk.TclError:
                pass

    def _bind_shortcuts(self) -> None:
        self.bind("<Escape>", lambda _e: self._close())

    def _center_on(self, master: tk.Misc | None) -> None:
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        # فضای قابل استفاده با احتساب حاشیهٔ امن (taskbar/dock).
        usable_w = max(screen_w - 2 * _EDGE_MARGIN, MIN_WIDTH)
        usable_h = max(screen_h - 2 * _EDGE_MARGIN, MIN_HEIGHT)

        width = max(self.winfo_reqwidth(), DEFAULT_WIDTH)
        height = max(self.winfo_reqheight(), DEFAULT_HEIGHT)
        width = min(width, usable_w)
        height = min(height, usable_h)

        parent_ok = False
        if master is not None:
            try:
                parent_ok = master.winfo_width() > 1 and master.winfo_viewable()
            except tk.TclError:
                parent_ok = False

        if parent_ok:
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 2
        else:
            x = (screen_w - width) // 2
            y = (screen_h - height) // 2

        # اطمینان از داخل‌بودن پنجره در محدودهٔ امن صفحه.
        x = max(_EDGE_MARGIN, min(x, screen_w - width - _EDGE_MARGIN))
        y = max(_EDGE_MARGIN, min(y, screen_h - height - _EDGE_MARGIN))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _close(self) -> None:
        # لغو هر timer معلق پیش از destroy (جلوگیری از TclError).
        if self._status_after_id is not None:
            try:
                self.after_cancel(self._status_after_id)
            except tk.TclError:
                pass
            self._status_after_id = None
        self.destroy()

    # ------------------------------------------------------------- layout --
    def _build(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        contents: tuple[str, ...] = (
            self._quick_start(),
            self._transactions(),
            self._products(),
            self._faq(),
        )
        if len(contents) != len(self._TAB_TITLES):
            # نقض invariant — بهتر است در تست‌ها شناسایی شود تا در زمان اجرا.
            logger.error(
                "HelpWindow tab titles/content mismatch: %d vs %d",
                len(self._TAB_TITLES), len(contents),
            )

        for title, content in zip(self._TAB_TITLES, contents):
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            self._texts.append(self._scrollable_text(frame, content))

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, padx=10, pady=(0, 4))
        ttk.Button(
            buttons, text="بستن", style="Secondary.TButton",
            command=self._close,
        ).pack(side=tk.RIGHT, padx=4)
        ttk.Button(
            buttons, text="کپی همه متن", style="Primary.TButton",
            command=self._copy_all,
        ).pack(side=tk.RIGHT, padx=4)

        # نوار وضعیت کوچک برای بازخورد غیرمسدودکننده (به‌جای messagebox).
        status = ttk.Label(self, textvariable=self._status_var,
                           style="Muted.TLabel", anchor="e")
        status.pack(fill=tk.X, padx=14, pady=(0, 8))

    @staticmethod
    def _scrollable_text(parent: ttk.Frame, content: str) -> tk.Text:
        wrap = ttk.Frame(parent)
        wrap.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(wrap)
        text = tk.Text(
            wrap,
            wrap=tk.WORD,
            justify=tk.RIGHT,
            font=T.FONT,
            bg=T.CARD_BG,
            fg=T.TEXT,
            selectbackground=T.ACCENT if hasattr(T, "ACCENT") else None,
            insertbackground=T.TEXT,
            yscrollcommand=scrollbar.set,
            padx=12,
            pady=12,
            spacing1=2,
            spacing3=2,
            relief=tk.FLAT,
            cursor="arrow",
        )
        scrollbar.config(command=text.yview)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text.insert("1.0", content)
        text.config(state=tk.DISABLED)

        def select_all(_event=None):
            # در حالت disabled، لازم است موقتاً به normal سوییچ کنیم.
            text.config(state=tk.NORMAL)
            text.tag_add(tk.SEL, "1.0", "end-1c")
            text.mark_set(tk.INSERT, "1.0")
            text.see("1.0")
            text.config(state=tk.DISABLED)
            return "break"

        text.bind("<Control-a>", select_all)
        text.bind("<Control-A>", select_all)
        return text

    # ------------------------------------------------------------ actions --
    def _set_status(self, message: str) -> None:
        self._status_var.set(message)
        if self._status_after_id is not None:
            try:
                self.after_cancel(self._status_after_id)
            except tk.TclError:
                pass
        try:
            self._status_after_id = self.after(
                _STATUS_CLEAR_MS, lambda: self._status_var.set("")
            )
        except tk.TclError:
            self._status_after_id = None

    def _collect_all(self) -> str:
        """محتوای همهٔ تب‌ها را با عنوان‌ها می‌چسباند (منبع واحد برای کپی)."""
        parts: list[str] = []
        for title, widget in zip(self._TAB_TITLES, self._texts):
            try:
                body = widget.get("1.0", "end-1c")
            except tk.TclError:
                body = ""
            parts.append(f"=== {title} ===\n{body}")
        return "\n\n".join(parts)

    def _copy_all(self) -> None:
        payload = self._collect_all()
        try:
            self.clipboard_clear()
            self.clipboard_append(payload)
            # روی X11، محتوا فقط تا زمانی که مالک پنجره زنده است در clipboard
            # می‌ماند؛ استفاده از update() آن را تثبیت می‌کند.
            self.update_idletasks()
        except tk.TclError:
            logger.exception("Clipboard copy failed")
            messagebox.showerror(
                "کپی ناموفق",
                "دسترسی به کلیپ‌بورد ممکن نشد. لطفاً دوباره تلاش کنید.",
                parent=self,
            )
            return
        self._set_status("متن کامل راهنما در کلیپ‌بورد کپی شد.")

    # ------------------------------------------------------------ content --
    @staticmethod
    def _quick_start() -> str:
        return (
            "شروع سریع\n"
            "=========\n\n"
            "۱) از Combobox کالا را انتخاب کنید (نمایش به صورت «کد - نام»).\n"
            "۲) نوع تراکنش را مشخص کنید: ورود / خروج / عودت.\n"
            "۳) تعداد را وارد کنید (فقط عدد مثبت).\n"
            "۴) در صورت نیاز تاریخ و توضیح را تکمیل کنید.\n"
            "۵) دکمه «ثبت» را بزنید.\n\n"
            "پس از انتخاب کالا، موجودی فعلی، واحد، حداقل و قفسه به‌صورت خودکار نمایش داده می‌شود.\n"
            "رنگ موجودی:\n"
            "  • سبز = مناسب\n"
            "  • نارنجی = کمتر از حداقل\n"
            "  • قرمز = منفی یا بحرانی\n"
        )

    @staticmethod
    def _transactions() -> str:
        return (
            "ثبت تراکنش\n"
            "==========\n\n"
            "• ورود (IN): افزایش موجودی (خرید یا دریافت).\n"
            "• خروج (OUT): کاهش موجودی (مصرف یا تحویل).\n"
            "• عودت (RETURN): بازگشت کالا به انبار (افزایش موجودی).\n\n"
            "مثال:\n"
            "  موجودی دستمال = ۱۰۰\n"
            "  خروج ۲۰ → موجودی ۸۰\n"
            "  عودت ۵ → موجودی ۸۵\n\n"
            "اگر خروج باعث موجودی منفی شود، هشدار نمایش داده می‌شود.\n"
            "اگر موجودی زیر حداقل مجاز برود، هشدار کمبود نمایش داده می‌شود.\n"
        )

    @staticmethod
    def _products() -> str:
        return (
            "مدیریت کالاها\n"
            "=============\n\n"
            "• کد کالا را کاربر تعیین می‌کند؛ کد تکراری یا نام تکراری هشدار می‌دهد،\n"
            "  اما با تأیید کاربر قابل ثبت است.\n"
            "• نام کالا نباید تکراری باشد.\n"
            "• حداقل موجودی (min_stock) برای هشدار کمبود استفاده می‌شود.\n"
            "• دسته: مصرفی / تکنیکال / عمومی\n"
            "• قفسه: محل فیزیکی در انبار (اختیاری)\n\n"
            "از منوی «کالاها» می‌توانید لیست، ویرایش و حذف انجام دهید.\n"
            "کالایی که تراکنش دارد قابل حذف نیست.\n"
        )

    @staticmethod
    def _faq() -> str:
        return (
            "سوالات متداول\n"
            "=============\n\n"
            "س: پایگاه داده کجاست؟\n"
            "ج: در ویندوز: %APPDATA%\\EasyWarehouse\\anbar.db\n"
            "   در لینوکس: ~/.local/share/EasyWarehouse/anbar.db\n\n"
            "س: چطور پشتیبان بگیرم؟\n"
            "ج: منوی پرونده → پشتیبان‌گیری\n\n"
            "س: موجودی منفی یعنی چه؟\n"
            "ج: خروج بیش از موجودی ثبت شده؛ باید موجودی را اصلاح یا ورود ثبت کنید.\n\n"
            "س: انتقال به سیستم دیگر؟\n"
            "ج: فایل پشتیبان .db را کپی و از منوی پرونده → بازیابی استفاده کنید.\n\n"
            "س: کلید میانبر راهنما؟\n"
            "ج: F1\n"
        )
