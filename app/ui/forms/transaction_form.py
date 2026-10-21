# -*- coding: utf-8 -*-
"""فرم حرفه‌ای ثبت گردش کالا؛ لایهٔ نمایش مستقل از منطق ثبت."""

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
    """فرم کارت‌مانند و بخش‌بندی‌شدهٔ ثبت تراکنش انبار."""

    INFO_EMPTY = "ابتدا کالا را انتخاب کنید تا موجودی و مشخصات آن نمایش داده شود."

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
            master, text="  ثبت گردش کالا  ", style="Card.TLabelframe",
            padding=(16, 14), **kwargs
        )
        self.ps, self.ts, self.on_ok = product_svc, tx_svc, on_ok
        self.on_manage_products = on_manage_products
        self._cat: Optional[str] = None
        self._items: list[dict] = []
        self._build()
        self.refresh()

    # ----------------------------------------------------------------- layout

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        # Intro / hierarchy
        intro = tk.Frame(self, bg=T.CARD_BG)
        intro.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        intro.columnconfigure(0, weight=1)
        tk.Label(
            intro, text="ثبت ورود، خروج و گردش کالا", bg=T.CARD_BG,
            fg=T.TEXT, font=T.FONT_SECTION, anchor="e",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            intro, text="اطلاعات را بررسی کنید؛ موجودی پس از ثبت به‌روزرسانی می‌شود.",
            bg=T.CARD_BG, fg=T.TEXT_MUTED, font=T.FONT_SMALL, anchor="e",
        ).grid(row=1, column=0, sticky="ew", pady=(3, 0))

        # Transaction type
        type_box = tk.Frame(
            self, bg=T.BG, highlightbackground=T.CARD_BORDER,
            highlightthickness=1, padx=12, pady=9,
        )
        type_box.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        type_box.columnconfigure(1, weight=1)
        tk.Label(
            type_box, text="نوع گردش", bg=T.BG, fg=T.TEXT,
            font=T.FONT_BOLD, anchor="e",
        ).grid(row=0, column=2, sticky="e", padx=(10, 0))
        default_type = next(iter(TYPES), "IN")
        self.type_var = tk.StringVar(value=default_type)
        radio_frame = tk.Frame(type_box, bg=T.BG)
        radio_frame.grid(row=0, column=1, sticky="e")
        for k, v in TYPES.items():
            ttk.Radiobutton(
                radio_frame, text=v, variable=self.type_var, value=k,
            ).pack(side=tk.RIGHT, padx=(0, 12))

        # Product selector
        tk.Label(
            self, text="کالا *", bg=T.CARD_BG, fg=T.TEXT,
            font=T.FONT_BOLD, anchor="e",
        ).grid(row=2, column=0, sticky="e", pady=(0, 5))
        self.prod_var = tk.StringVar()
        self.combo = ttk.Combobox(
            self, textvariable=self.prod_var, state="readonly",
            font=T.FONT, height=14,
        )
        self.combo.grid(row=3, column=0, sticky="ew", ipady=4, pady=(0, 10))
        self.combo.bind("<<ComboboxSelected>>", self._on_select)

        # Live stock information panel
        self.stock_panel = tk.Frame(
            self, bg="#F0F9FA", highlightbackground="#B8E2E5",
            highlightthickness=1, padx=12, pady=10,
        )
        self.stock_panel.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        self.stock_panel.columnconfigure(0, weight=1)
        tk.Label(
            self.stock_panel, text="وضعیت کالا", bg="#F0F9FA",
            fg=T.PRIMARY, font=T.FONT_BOLD, anchor="e",
        ).grid(row=0, column=0, sticky="ew")
        self.info = tk.Label(
            self.stock_panel, text=self.INFO_EMPTY, font=T.FONT_SMALL,
            fg=T.TEXT_MUTED, bg="#F0F9FA", anchor="e", justify="right",
            wraplength=620,
        )
        self.info.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        # Compact two-column input area
        fields = tk.Frame(self, bg=T.CARD_BG)
        fields.grid(row=5, column=0, sticky="ew")
        fields.columnconfigure(0, weight=1, uniform="transaction_fields")
        fields.columnconfigure(1, weight=1, uniform="transaction_fields")

        tk.Label(
            fields, text="مقدار *", bg=T.CARD_BG, fg=T.TEXT,
            font=T.FONT_BOLD, anchor="e",
        ).grid(row=0, column=0, sticky="ew", padx=(8, 0), pady=(0, 5))
        tk.Label(
            fields, text="تاریخ شمسی *", bg=T.CARD_BG, fg=T.TEXT,
            font=T.FONT_BOLD, anchor="e",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(0, 5))

        self.qty_var = tk.StringVar()
        self._qty_entry = ttk.Entry(
            fields, textvariable=self.qty_var, justify="right",
        )
        self._qty_entry.grid(
            row=1, column=0, sticky="ew", padx=(8, 0), ipady=4, pady=(0, 10)
        )
        self._qty_entry.bind("<Return>", lambda _e: self._submit())

        self.date_var = tk.StringVar(value=today_jalali())
        self._date_entry = ttk.Entry(
            fields, textvariable=self.date_var, justify="right",
        )
        self._date_entry.grid(
            row=1, column=1, sticky="ew", padx=(0, 8), ipady=4, pady=(0, 10)
        )
        self._date_entry.bind("<Return>", lambda _e: self._submit())

        tk.Label(
            self, text="توضیحات", bg=T.CARD_BG, fg=T.TEXT,
            font=T.FONT_BOLD, anchor="e",
        ).grid(row=6, column=0, sticky="e", pady=(0, 5))
        self.note_var = tk.StringVar()
        self._note_entry = ttk.Entry(
            self, textvariable=self.note_var,
            justify="right",
        )
        self._note_entry.grid(row=7, column=0, sticky="ew", ipady=4)
        self._note_entry.bind("<Return>", lambda _e: self._submit())

        # Multi-line document cart.
        cart = tk.Frame(self, bg=T.CARD_BG)
        cart.grid(row=8, column=0, sticky="ew", pady=(4, 0))
        tk.Label(
            cart, text="اقلام سند (برای افزودن هر کالا «افزودن قلم» را بزنید)",
            bg=T.CARD_BG, fg=T.TEXT, font=T.FONT_BOLD, anchor="e",
        ).pack(fill=tk.X)
        self.cart_list = tk.Listbox(
            cart, height=4, font=T.FONT, bg=T.CARD_BG, fg=T.TEXT,
            activestyle="none", selectbackground=T.PRIMARY,
        )
        self.cart_list.pack(fill=tk.X, pady=(4, 4))
        cart_actions = ttk.Frame(cart)
        cart_actions.pack(fill=tk.X)
        ttk.Button(
            cart_actions, text="افزودن قلم", style="Secondary.TButton",
            command=self._add_line,
        ).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(
            cart_actions, text="حذف قلم انتخاب‌شده", style="Ghost.TButton",
            command=self._remove_line,
        ).pack(side=tk.RIGHT)
        self.cart_count = ttk.Label(cart_actions, text="۰ قلم")
        self.cart_count.pack(side=tk.LEFT)

        # Document metadata persisted with each stock movement.
        document_fields = tk.Frame(self, bg=T.CARD_BG)
        document_fields.grid(row=9, column=0, sticky="ew", pady=(10, 0))
        document_fields.columnconfigure(0, weight=1, uniform="document_fields")
        document_fields.columnconfigure(1, weight=1, uniform="document_fields")
        tk.Label(document_fields, text="طرف حساب / واحد", bg=T.CARD_BG,
                 fg=T.TEXT, font=T.FONT_BOLD, anchor="e").grid(
            row=0, column=0, sticky="ew", padx=(8, 0), pady=(0, 5))
        tk.Label(document_fields, text="شماره مرجع (اختیاری)", bg=T.CARD_BG,
                 fg=T.TEXT, font=T.FONT_BOLD, anchor="e").grid(
            row=0, column=1, sticky="ew", padx=(0, 8), pady=(0, 5))
        self.party_var, self.reference_var = tk.StringVar(), tk.StringVar()
        ttk.Entry(document_fields, textvariable=self.party_var, justify="right").grid(
            row=1, column=0, sticky="ew", padx=(8, 0), ipady=4, pady=(0, 10))
        ttk.Entry(document_fields, textvariable=self.reference_var, justify="right").grid(
            row=1, column=1, sticky="ew", padx=(0, 8), ipady=4, pady=(0, 10))
        tk.Label(document_fields, text="تحویل‌دهنده", bg=T.CARD_BG,
                 fg=T.TEXT, font=T.FONT_BOLD, anchor="e").grid(
            row=2, column=0, sticky="ew", padx=(8, 0), pady=(0, 5))
        tk.Label(document_fields, text="تحویل‌گیرنده", bg=T.CARD_BG,
                 fg=T.TEXT, font=T.FONT_BOLD, anchor="e").grid(
            row=2, column=1, sticky="ew", padx=(0, 8), pady=(0, 5))
        self.delivered_var, self.received_var = tk.StringVar(), tk.StringVar()
        ttk.Entry(document_fields, textvariable=self.delivered_var, justify="right").grid(
            row=3, column=0, sticky="ew", padx=(8, 0), ipady=4, pady=(0, 4))
        ttk.Entry(document_fields, textvariable=self.received_var, justify="right").grid(
            row=3, column=1, sticky="ew", padx=(0, 8), ipady=4, pady=(0, 4))

        # Actions
        ttk.Separator(self, orient="horizontal").grid(
            row=10, column=0, sticky="ew", pady=(14, 10)
        )
        actions = ttk.Frame(self)
        actions.grid(row=11, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        ttk.Button(
            actions, text="✓  ثبت قطعی سند", style="Primary.TButton",
            command=self._submit,
        ).grid(row=0, column=2, padx=(6, 0), sticky="e")
        ttk.Button(
            actions, text="پاک کردن فرم", style="Secondary.TButton",
            command=self._clear,
        ).grid(row=0, column=1, padx=6, sticky="e")
        ttk.Button(
            actions, text="مدیریت کالاها", style="Ghost.TButton",
            command=self._manage_products,
        ).grid(row=0, column=0, sticky="w")

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
        status = "بحرانی" if p.is_critical() else "کم" if p.is_low() else "مناسب"
        self.info.config(
            text=(
                f"موجودی فعلی: {p.stock:g} {p.unit}   •   "
                f"حداقل موجودی: {p.min_stock:g}   •   "
                f"قفسه: {p.shelf or '—'}   •   وضعیت: {status}"
            ),
            fg=color,
        )

    # ----------------------------------------------------------------- submit

    def _add_line(self) -> None:
        code = self.ps.code_from_label(self.prod_var.get())
        if not code:
            self._show_error("لطفاً یک کالا انتخاب کنید.")
            return
        try:
            qty = parse_positive_qty(self.qty_var.get())
        except ValueError as exc:
            self._show_error(str(exc))
            return
        product = self.ps.get(code)
        if product is None:
            self._show_error("کالای انتخاب‌شده دیگر در فهرست وجود ندارد.")
            return
        if self._items and self._items[0]["type"] != self.type_var.get():
            self._show_error("نوع سند را نمی‌توان پس از افزودن قلم تغییر داد؛ ابتدا اقلام را پاک کنید.")
            return
        self._items.append({
            "code": code, "name": product.name, "unit": product.unit,
            "type": self.type_var.get(), "qty": qty,
        })
        self._refresh_cart()
        self.qty_var.set("")
        self.prod_var.set("")
        self._show_empty_info()
        self.combo.focus_set()

    def _remove_line(self) -> None:
        selected = self.cart_list.curselection()
        if not selected:
            self._show_error("ابتدا یک قلم از فهرست سند انتخاب کنید.")
            return
        del self._items[selected[0]]
        self._refresh_cart()

    def _refresh_cart(self) -> None:
        self.cart_list.delete(0, tk.END)
        for index, item in enumerate(self._items, 1):
            kind = TYPES.get(item["type"], item["type"])
            self.cart_list.insert(
                tk.END, f"{index}. {item['name']} | {kind} | {item['qty']:g} {item['unit']}"
            )
        self.cart_count.config(text=f"{len(self._items)} قلم")

    def _submit(self) -> None:
        items = list(self._items)
        # Backward-compatible shortcut: the selected item can be posted as a one-line document.
        if not items and self.prod_var.get().strip():
            code = self.ps.code_from_label(self.prod_var.get())
            try:
                qty = parse_positive_qty(self.qty_var.get())
            except ValueError as exc:
                self._show_error(str(exc))
                return
            items.append({"code": code, "type": self.type_var.get(), "qty": qty})
        if not items:
            self._show_error("برای ثبت سند، دست‌کم یک قلم کالا اضافه کنید.")
            return
        try:
            tx_date = validate_transaction_date(from_jalali(self.date_var.get()))
        except ValueError as exc:
            self._show_error(str(exc))
            return
        try:
            saved, warnings, document_no = self.ts.add_document(
                items,
                date_str=tx_date,
                note=self.note_var.get().strip(),
                party_name=self.party_var.get().strip(),
                delivered_by=self.delivered_var.get().strip(),
                received_by=self.received_var.get().strip(),
                reference_no=self.reference_var.get().strip(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Warehouse document post failed")
            self._show_error(str(exc))
            return

        summary = f"سند {document_no} با {len(saved)} قلم ثبت قطعی شد."
        if warnings:
            messagebox.showwarning(
                "سند ثبت شد با هشدار",
                summary + "\n\n" + "\n".join(warnings),
                parent=self.winfo_toplevel(),
            )
        else:
            messagebox.showinfo("ثبت سند", summary, parent=self.winfo_toplevel())
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
        self._items.clear()
        self._refresh_cart()
        self.party_var.set("")
        self.reference_var.set("")
        self.delivered_var.set("")
        self.received_var.set("")
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
