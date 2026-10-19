# -*- coding: utf-8 -*-
"""پنجره راهنمای کاربر (F1)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from app.ui import theme as T


class HelpWindow(tk.Toplevel):
    """راهنمای غیرمودال با ۴ تب فارسی."""

    def __init__(self, master: Optional[tk.Misc] = None) -> None:
        super().__init__(master)
        self.title("راهنمای کاربر - EasyWarehouse")
        self.geometry("800x600")
        self.minsize(640, 480)
        self.configure(bg=T.BG)
        if master:
            self.transient(master)

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tabs = [
            ("شروع سریع", self._quick_start),
            ("ثبت تراکنش", self._transactions),
            ("مدیریت کالاها", self._products),
            ("سوالات متداول", self._faq),
        ]
        for title, builder in tabs:
            frame = ttk.Frame(nb)
            nb.add(frame, text=title)
            self._scrollable_text(frame, builder())

        bf = ttk.Frame(self)
        bf.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(bf, text="بستن", style="Secondary.TButton", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bf, text="چاپ راهنما", style="Primary.TButton", command=self._print).pack(side=tk.RIGHT, padx=4)

    def _scrollable_text(self, parent: ttk.Frame, content: str) -> None:
        wrap = ttk.Frame(parent)
        wrap.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(wrap)
        txt = tk.Text(
            wrap,
            wrap=tk.WORD,
            font=T.FONT,
            bg=T.CARD_BG,
            fg=T.TEXT,
            yscrollcommand=sb.set,
            padx=12,
            pady=12,
            relief=tk.FLAT,
        )
        sb.config(command=txt.yview)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        txt.insert("1.0", content)
        txt.config(state=tk.DISABLED)

    def _print(self) -> None:
        messagebox.showinfo(
            "چاپ",
            "متن راهنما را می‌توانید از تب‌ها کپی کنید یا از منوی پرونده پشتیبان بگیرید.\n"
            "برای چاپ مستقیم، از قابلیت چاپ سیستم‌عامل روی متن کپی‌شده استفاده کنید.",
            parent=self,
        )

    @staticmethod
    def _quick_start() -> str:
        return (
            "شروع سریع EasyWarehouse\n"
            "========================\n\n"
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
            "• کد کالا را کاربر تعیین می‌کند؛ کد تکراری یا نام تکراری هشدار می‌دهد، اما با تأیید کاربر قابل ثبت است.\n"
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
            "س: دیتابیس کجاست؟\n"
            "ج: در ویندوز مسیر %%APPDATA%%\\EasyWarehouse\\anbar.db\n"
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
