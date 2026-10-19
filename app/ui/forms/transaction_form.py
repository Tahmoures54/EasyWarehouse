# -*- coding: utf-8 -*-
"""فرم ثبت تراکنش با Combobox."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from typing import Callable, Optional

from app.config import TYPES
from app.services.product_service import ProductService
from app.services.transaction_service import TransactionService, parse_positive_qty, validate_transaction_date
from app.ui import theme as T


class TransactionForm(ttk.LabelFrame):
    """فرم کارت‌مانند ثبت تراکنش."""

    def __init__(self, master: tk.Misc, product_svc: ProductService,
                 tx_svc: TransactionService, on_ok: Optional[Callable[[], None]] = None, **kwargs) -> None:
        super().__init__(master, text=" ثبت تراکنش ", style="Card.TLabelframe", padding=12, **kwargs)
        self.ps, self.ts, self.on_ok = product_svc, tx_svc, on_ok
        self._cat: Optional[str] = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        ttk.Label(self, text="نوع:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.type_var = tk.StringVar(value="IN")
        rf = ttk.Frame(self)
        rf.grid(row=0, column=1, sticky="w")
        for k, v in TYPES.items():
            ttk.Radiobutton(rf, text=v, variable=self.type_var, value=k).pack(side=tk.LEFT, padx=6)

        ttk.Label(self, text="کالا:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.prod_var = tk.StringVar()
        self.combo = ttk.Combobox(self, textvariable=self.prod_var, state="readonly", width=42)
        self.combo.grid(row=1, column=1, sticky="w", pady=4)
        self.combo.bind("<<ComboboxSelected>>", self._on_select)

        self.info = tk.Label(self, text="موجودی: —  |  واحد: —  |  حداقل: —  |  قفسه: —",
                             font=T.FONT, fg=T.TEXT_MUTED, bg=T.CARD_BG, anchor="w")
        self.info.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=2)
        ttk.Label(self, text="مقدار:").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        self.qty_var = tk.StringVar()
        qty_entry = ttk.Entry(self, textvariable=self.qty_var, width=14)
        qty_entry.grid(row=3, column=1, sticky="w", pady=4)
        qty_entry.bind("<Return>", lambda _event: self._submit())
        ttk.Label(self, text="تاریخ (YYYY-MM-DD):").grid(row=4, column=0, sticky="e", padx=4, pady=4)
        self.date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(self, textvariable=self.date_var, width=14).grid(row=4, column=1, sticky="w", pady=4)
        ttk.Label(self, text="توضیح:").grid(row=5, column=0, sticky="e", padx=4, pady=4)
        self.note_var = tk.StringVar()
        note_entry = ttk.Entry(self, textvariable=self.note_var, width=42)
        note_entry.grid(row=5, column=1, sticky="w", pady=4)
        note_entry.bind("<Return>", lambda _event: self._submit())
        bf = ttk.Frame(self)
        bf.grid(row=6, column=0, columnspan=2, pady=10)
        ttk.Button(bf, text="ثبت تراکنش", style="Primary.TButton", command=self._submit, width=14).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text="پاک کردن", style="Secondary.TButton", command=self._clear, width=10).pack(side=tk.LEFT, padx=4)

    def refresh(self, category: Optional[str] = None) -> None:
        self._cat = category
        self.combo["values"] = self.ps.combo_items(category)

    def _on_select(self, _event=None) -> None:
        code = self.ps.code_from_label(self.prod_var.get())
        p = self.ps.get(code) if code else None
        if not p:
            self.info.config(text="موجودی: —  |  واحد: —  |  حداقل: —  |  قفسه: —", fg=T.TEXT_MUTED)
            return
        color = T.STOCK_CRIT if p.is_critical() else T.STOCK_LOW if p.is_low() else T.STOCK_OK
        self.info.config(text=f"موجودی: {p.stock:g}  |  واحد: {p.unit}  |  حداقل: {p.min_stock:g}  |  قفسه: {p.shelf or '—'}", fg=color)

    def _submit(self) -> None:
        code = self.ps.code_from_label(self.prod_var.get())
        if not code:
            messagebox.showerror("خطا", "لطفاً یک کالا انتخاب کنید.")
            return
        try:
            qty = parse_positive_qty(self.qty_var.get())
            tx_date = validate_transaction_date(self.date_var.get())
            tx, warn = self.ts.add(code, self.type_var.get(), qty, tx_date, self.note_var.get().strip())
        except Exception as exc:
            messagebox.showerror("خطا", str(exc))
            return
        if warn:
            messagebox.showwarning("هشدار موجودی", warn)
        messagebox.showinfo("ثبت شد", f"{tx.type_fa()} به مقدار {tx.qty:g} {tx.unit} ثبت شد.")
        self._clear(preserve_type=True)
        self.combo.focus_set()
        if self.on_ok:
            self.on_ok()

    def _clear(self, preserve_type: bool = False) -> None:
        previous_type = self.type_var.get()
        self.prod_var.set("")
        self.qty_var.set("")
        self.note_var.set("")
        self.date_var.set(date.today().isoformat())
        if not preserve_type:
            self.type_var.set("IN")
        else:
            self.type_var.set(previous_type)
        self.info.config(text="موجودی: —  |  واحد: —  |  حداقل: —  |  قفسه: —", fg=T.TEXT_MUTED)
