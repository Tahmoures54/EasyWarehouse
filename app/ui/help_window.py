# -*- coding: utf-8 -*-
"""پنجره راهنمای کاربر (F1)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from app.config import APP_NAME
from app.ui import theme as T


class HelpWindow(tk.Toplevel):
    """راهنمای غیرمودال با ۴ تب فارسی."""

    DEFAULT_WIDTH = 800
    DEFAULT_HEIGHT = 600
    MIN_WIDTH = 640
    MIN_HEIGHT = 480

    def __init__(self, master: Optional[tk.Misc] = None) -> None:
        super().__init__(master)
        self._texts: list[tk.Text] = []
        self._configure_window(master)
        self._build()
        self._bind_shortcuts()
        self._center_on(master)

    # ------------------------------------------------------------------ setup

    def _configure_window(self, master: Optional[tk.Misc]) -> None:
        self.title(f"راهنمای کاربر — {APP_NAME}")
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.configure(bg=T.BG)
        if master is not None:
            self.transient(master)

    def _bind_shortcuts(self) -> None:
        self.bind("<Escape>", lambda _e: self.destroy())

    def _center_on(self, master: Optional[tk.Misc]) -> None:
        self.update_idletasks()
        width = max(self.winfo_reqwidth(), self.DEFAULT_WIDTH)
        height = max(self.winfo_reqheight(), self.DEFAULT_HEIGHT)
        width = min(width, self.winfo_screenwidth())
        height = min(height, self.winfo_screenheight())

        if master is not None and master.winfo_width() > 1:
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 2
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")

    # ----------------------------------------------------------------- layout

    def _build(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tabs = (
            ("شروع سریع", self._quick_start()),
            ("ثبت تراکنش", self._transactions()),
            ("مدیریت کالاها", self._products()),
            ("سوالات متداول", self._faq()),
        )
        for title, content in tabs:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            self._texts.append(self._scrollable_text(frame, content))

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(
            buttons, text="بستن", style="Secondary.TButton",
            command=self.destroy,
        ).pack(side=tk.RIGHT, padx=4)
        ttk.Button(
            buttons, text="کپی همه متن", style="Primary.TButton",
            command=self._copy_all,
        ).pack(side=tk.RIGHT, padx=4)

    @staticmethod
    def _scrollable_text(parent: ttk.Frame, content: str) -> tk.Text:
        wrap = ttk.Frame(parent)
        wrap.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(wrap)
        text = tk.Text(
            wrap,
            wrap=tk.WORD,
            justify=tk.RIGHT,          # توجیه راست برای متن فارسی
            font=T.FONT,
            bg=T.CARD_BG,
            fg=T.TEXT,
            yscrollcommand=scrollbar.set,
            padx=12,
            pady=12,
            spacing1=2,
            spacing3=2,
            relief=tk.FLAT,
            cursor="arrow",             # غیرقابل‌ویرایش؛ I-beam گمراه‌کننده است
        )
        scrollbar.config(command=text.yview)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text.insert("1.0", content)
        text.config(state=tk.DISABLED)

        # Ctrl+A برای انتخاب همه (Ctrl+C پیش‌فرض کار می‌کند)
        def select_all(_event=None):
            text.tag_add(tk.SEL, "1.0", tk.END)
            text.mark_set(tk.INSERT, "1.0")
            return "break"

        text.bind("<Control-a>", select_all)
        text.bind("<Control-A>", select_all)
        return text

    # ---------------------------------------------------------------- actions

    def _copy_all(self) -> None:
        tabs = ("شروع سریع", "ثبت تراکنش", "مدیریت کالاها", "سوالات متداول")
        parts = [
            f"=== {title} ===\n{txt.get('1.0', 'end-1c')}"
            for title, txt in zip(tabs, self._texts)
        ]
        self.clipboard_clear()
        self.clipboard_append("\n\n".join(parts))
        messagebox.showinfo(
            "کپی شد",
            "متن کامل راهنما در کلیپ‌بورد قرار گرفت.",
            parent=self,
        )

    # -------------------------------------------------------------- content

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
