# -*- coding: utf-8 -*-
"""پنجره شمارش فیزیکی و ثبت تعدیل تأییدشده."""

from __future__ import annotations

import math
import uuid
import tkinter as tk
from tkinter import messagebox, ttk

from app.services.stock_adjustment_service import StockAdjustmentService


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class StockAdjustmentDialog(tk.Toplevel):
    def __init__(self, parent, products, db, current_user, on_saved=None):
        super().__init__(parent)
        self.title("شمارش و تعدیل موجودی")
        self.transient(parent)
        self.resizable(False, False)
        self.products = products
        self.current_user = current_user
        self.on_saved = on_saved
        self.service = StockAdjustmentService(db)
        self.reference = uuid.uuid4().hex
        self._items = products.all()
        self._by_label = {
            f"{p.user_code or p.code} — {p.name} [{p.code}]": p for p in self._items
        }
        self.product_var = tk.StringVar()
        self.count_var = tk.StringVar()
        self.reason_var = tk.StringVar()
        self.system_var = tk.StringVar(value="—")
        self.variance_var = tk.StringVar(value="اختلاف: —")
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="کالا").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.combo = ttk.Combobox(frame, textvariable=self.product_var, values=list(self._by_label), state="readonly", width=42)
        self.combo.grid(row=0, column=1, sticky="ew", padx=6, pady=6)
        self.combo.bind("<<ComboboxSelected>>", self._select_product)
        ttk.Label(frame, text="موجودی سیستمی").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Label(frame, textvariable=self.system_var).grid(row=1, column=1, sticky="w", padx=6, pady=6)
        ttk.Label(frame, text="تعداد شمارش‌شده").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        count_entry = ttk.Entry(frame, textvariable=self.count_var)
        count_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=6)
        count_entry.bind("<KeyRelease>", lambda _e: self._preview())
        count_entry.bind("<FocusOut>", lambda _e: self._preview())
        ttk.Label(frame, textvariable=self.variance_var).grid(row=3, column=1, sticky="w", padx=6, pady=6)
        ttk.Label(frame, text="علت تعدیل (اجباری)").grid(row=4, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(frame, textvariable=self.reason_var, width=44).grid(row=4, column=1, sticky="ew", padx=6, pady=6)
        ttk.Label(frame, text="پس از تأیید، یک سند قابل ردیابی ثبت می‌شود.").grid(row=5, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 12))
        actions = ttk.Frame(frame)
        actions.grid(row=6, column=0, columnspan=2, sticky="e")
        ttk.Button(actions, text="انصراف", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(actions, text="تأیید و ثبت تعدیل", command=self._submit).pack(side=tk.RIGHT, padx=4)
        if self._by_label:
            self.combo.current(0)
            self._select_product()

    def _selected(self):
        return self._by_label.get(self.product_var.get())

    def _select_product(self, _event=None):
        product = self._selected()
        self._snapshot = float(product.stock) if product else None
        self.system_var.set(f"{self._snapshot:g}" if self._snapshot is not None else "—")
        self._preview()

    def _parse_count(self):
        text = self.count_var.get().strip().translate(_DIGITS).replace("،", ".").replace(",", ".")
        if not text or text.count(".") > 1 or any(ch not in "0123456789." for ch in text):
            raise ValueError("تعداد شمارش‌شده را به‌صورت عدد صفر یا مثبت وارد کنید.")
        try:
            value = float(text)
        except ValueError as exc:
            raise ValueError("تعداد شمارش‌شده نامعتبر است.") from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError("تعداد شمارش‌شده باید صفر یا مثبت باشد.")
        return value

    def _preview(self):
        try:
            count = self._parse_count()
            if self._snapshot is None:
                self.variance_var.set("اختلاف: —")
                return
            variance = count - self._snapshot
            self.variance_var.set(f"اختلاف: {variance:+g} (مثبت=افزایش، منفی=کاهش)")
        except ValueError:
            self.variance_var.set("اختلاف: تعداد معتبر وارد کنید.")

    def _submit(self):
        product = self._selected()
        if not product:
            messagebox.showwarning("شمارش موجودی", "ابتدا کالا را انتخاب کنید.", parent=self)
            return
        try:
            counted = self._parse_count()
        except ValueError as exc:
            messagebox.showwarning("شمارش موجودی", str(exc), parent=self)
            return
        reason = self.reason_var.get().strip()
        if not reason:
            messagebox.showwarning("شمارش موجودی", "علت تعدیل الزامی است.", parent=self)
            return
        variance = counted - float(self._snapshot)
        prompt = (
            f"کالا: {product.name}\nموجودی مبنا: {self._snapshot:g}\n"
            f"شمارش واقعی: {counted:g}\nاختلاف: {variance:+g}\nعلت: {reason}\n\n"
            "سند تعدیل را ثبت می‌کنید؟"
        )
        if not messagebox.askyesno("تأیید تعدیل", prompt, parent=self):
            return
        try:
            result = self.service.create(
                product.code, counted, reason, self.current_user["username"],
                expected_system_stock=self._snapshot, reference=self.reference,
            )
        except Exception as exc:
            messagebox.showerror("ثبت تعدیل ناموفق", str(exc), parent=self)
            return
        messagebox.showinfo(
            "تعدیل ثبت شد",
            f"شماره پیگیری: {result['reference']}\n"
            f"موجودی قبلی: {result['system_stock']:g}\n"
            f"موجودی شمارش‌شده: {result['counted_stock']:g}\n"
            f"اختلاف: {result['variance']:+g}\n"
            + (f"شناسه گردش تعدیل: {result['transaction_id']}" if result["transaction_id"] else "موجودی تغییری نکرد؛ شمارش بدون اختلاف ثبت شد."),
            parent=self,
        )
        if self.on_saved:
            self.on_saved()
        self.destroy()
