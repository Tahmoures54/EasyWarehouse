# -*- coding: utf-8 -*-
"""فرم ثبت تراکنش با Combobox."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from app.config import TYPES
from app.models.product import Product
from app.services.product_service import ProductService
from app.services.transaction_service import (
    TransactionService,
    parse_positive_qty,
    validate_transaction_date,
)
from app.ui import theme as T
from app.utils.date_utils import from_jalali, today_jalali

logger = logging.getLogger(__name__)


class TransactionForm(ttk.LabelFrame):
    """فرم کارت‌مانند ثبت تراکنش."""

    INFO_EMPTY = "موجودی: —  |  واحد: —  |  حداقل: —  |  قفسه: —"

    def __init__(
        self,
        master: tk.Misc,
        product_svc: ProductService,
        tx_svc: TransactionService,
        on_ok: Optional[Callable[[], None]] = None,
        on_manage_products: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master, text=" ثبت تراکنش ", style="Card.TLabelframe", padding=12, **kwargs
        )
        self.ps, self.ts, self.on_ok = product_svc, tx_svc, on_ok
        self.on_manage_products = on_manage_products
        self._cat: Optional[str] = None
        self._build()
        self.refresh()

    # ----------------------------------------------------------------- layout

    def _build(self) -> None:
        ttk.Label(self, text="نوع:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        default_type = next(iter(TYPES), "IN")
        self.type_var = tk.StringVar(value=default_type)
        rf = ttk.Frame(self)
        rf.grid(row=0, column=1, sticky="w")
        for k, v in TYPES.items():
            ttk.Radiobutton(rf, text=v, variable=self.type_var, value=k).pack(
                side=tk.LEFT, padx=6
            )

        ttk.Label(self, text="کالا:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.prod_var = tk.StringVar()
        self.combo = ttk.Combobox(
            self, textvariable=self.prod_var, state="readonly", width=42
        )
        self.combo.grid(row=1, column=1, sticky="w", pady=4)
        self.combo.bind("<<ComboboxSelected>>", self._on_select)

        self.info = tk.Label(
            self,
            text=self.INFO_EMPTY,
            font=T.FONT,
            fg=T.TEXT_MUTED,
            bg=T.CARD_BG,
            anchor="w",
        )
        self.info.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=2)

        ttk.Label(self, text="مقدار:").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        self.qty_var = tk.StringVar()
        self._qty_entry = ttk.Entry(self, textvariable=self.qty_var, width=14)
        self._qty_entry.grid(row=3, column=1, sticky="w", pady=4)
        self._qty_entry.bind("<Return>", lambda _e: self._submit())

        ttk.Label(self, text="تاریخ خورشیدی (سال/ماه/روز):").grid(
            row=4, column=0, sticky="e", padx=4, pady=4
        )
        self.date_var = tk.StringVar(value=today_jalali())
        self._date_entry = ttk.Entry(self, textvariable=self.date_var, width=14)
        self._date_entry.grid(row=4, column=1, sticky="w", pady=4)
        self._date_entry.bind("<Return>", lambda _e: self._submit())

        ttk.Label(self, text="توضیح:").grid(row=5, column=0, sticky="e", padx=4, pady=4)
        self.note_var = tk.StringVar()
        self._note_entry = ttk.Entry(self, textvariable=self.note_var, width=42)
        self._note_entry.grid(row=5, column=1, sticky="w", pady=4)
        self._note_entry.bind("<Return>", lambda _e: self._submit())

        bf = ttk.Frame(self)
        bf.grid(row=6, column=0, columnspan=2, pady=10)
        ttk.Button(
            bf, text="ثبت تراکنش", style="Primary.TButton",
            command=self._submit, width=14,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            bf, text="پاک کردن", style="Secondary.TButton",
            command=self._clear, width=10,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            bf,
            text="فهرست و کدگذاری کالا",
            style="Secondary.TButton",
            command=self._manage_products,
        ).pack(side=tk.LEFT, padx=4)

    # -------------------------------------------------------------- selection

    def refresh(self, category: Optional[str] = None) -> None:
        """به‌روزرسانی لیست کالاها؛ انتخاب فعلی در صورت امکان حفظ می‌شود."""
        self._cat = category
        items = self.ps.combo_items(category)
        current = self.prod_var.get()
        self.combo["values"] = items
        if current and current not in items:
            self.prod_var.set("")
        self._update_info()

    def _current_product(self) -> Optional[Product]:
        code = self.ps.code_from_label(self.prod_var.get())
        return self.ps.get(code) if code else None

    def _on_select(self, _event=None) -> None:
        p = self._current_product()
        if p is None:
            self.prod_var.set("")
            self._show_empty_info()
            return
        self._show_info(p)
        self._qty_entry.focus_set()

    def _update_info(self) -> None:
        p = self._current_product()
        if p is None:
            self._show_empty_info()
        else:
            self._show_info(p)

    def _show_empty_info(self) -> None:
        self.info.config(text=self.INFO_EMPTY, fg=T.TEXT_MUTED)

    def _show_info(self, p: Product) -> None:
        color = (
            T.STOCK_CRIT
            if p.is_critical()
            else T.STOCK_LOW
            if p.is_low()
            else T.STOCK_OK
        )
        self.info.config(
            text=(
                f"موجودی: {p.stock:g}  |  واحد: {p.unit}  |  "
                f"حداقل: {p.min_stock:g}  |  قفسه: {p.shelf or '—'}"
            ),
            fg=color,
        )

    # ----------------------------------------------------------------- submit

    def _submit(self) -> None:
        code = self.ps.code_from_label(self.prod_var.get())
        if not code:
            self._show_error("لطفاً یک کالا انتخاب کنید.")
            return

        try:
            qty = parse_positive_qty(self.qty_var.get())
            tx_date = validate_transaction_date(from_jalali(self.date_var.get()))
        except ValueError as exc:
            self._show_error(str(exc))
            return

        try:
            tx, warn = self.ts.add(
                code,
                self.type_var.get(),
                qty,
                tx_date,
                self.note_var.get().strip(),
            )
        except Exception as exc:  # noqa: BLE001 — نمایش خطای دامنه به کاربر
            logger.exception("Transaction add failed")
            self._show_error(str(exc))
            return

        summary = f"{tx.type_fa()} به مقدار {tx.qty:g} {tx.unit} ثبت شد."
        if warn:
            messagebox.showwarning(
                "ثبت شد با هشدار",
                f"{summary}\n\n{warn}",
                parent=self.winfo_toplevel(),
            )
        else:
            messagebox.showinfo("ثبت شد", summary, parent=self.winfo_toplevel())

        self._clear(preserve_type=True)
        try:
            if self.on_ok is not None:
                self.on_ok()
        except Exception:
            logger.exception("on_ok callback failed")

    def _clear(self, preserve_type: bool = False) -> None:
        self.prod_var.set("")
        self.qty_var.set("")
        self.note_var.set("")
        self.date_var.set(today_jalali())
        if not preserve_type:
            self.type_var.set(next(iter(TYPES), "IN"))
        self._show_empty_info()
        self.combo.focus_set()

    # ---------------------------------------------------------------- helpers

    def _manage_products(self) -> None:
        """فهرست کدگذاری را باز کن و پس از بازگشت، گزینه‌های کالا را تازه کن."""
        if self.on_manage_products is None:
            messagebox.showinfo(
                "فهرست کالاها",
                "دسترسی به فهرست و کدگذاری کالا در این فرم پیکربندی نشده است.",
                parent=self.winfo_toplevel(),
            )
            return
        self.on_manage_products()
        self.refresh()

    def _show_error(self, message: str) -> None:
        messagebox.showerror("خطا", message, parent=self.winfo_toplevel())
