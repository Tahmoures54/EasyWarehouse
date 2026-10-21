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


def _tok(name: str, default):
    return getattr(T, name, default)


class TransactionForm(ttk.LabelFrame):
    """فرم کارت‌مانند و بخش‌بندی‌شدهٔ ثبت تراکنش انبار."""

    INFO_EMPTY = "برای مشاهدهٔ موجودی و وضعیت کالا، یک کالا انتخاب کنید."
    INFO_NO_ITEMS = "هنوز قلمی به سند اضافه نشده است."
    STATUS_CLEAR_MS = 4000

    # --------------------------------------------------------------------- init

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
        self.ps = product_svc
        self.ts = tx_svc
        self.on_ok = on_ok
        self.on_manage_products = on_manage_products

        self._cat: Optional[str] = None
        self._items: list[dict] = []
        self._type_radios: list[ttk.Radiobutton] = []
        self._submitting = False
        self._status_after_id: Optional[str] = None

        self._build()
        self.refresh()
        self._refresh_cart()
        self._qty_entry.focus_set()

    # ------------------------------------------------------------------ layout

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._build_header(self).grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._build_type_bar(self).grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self._build_workspace(self).grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        self._build_metadata(self).grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self._build_status(self).grid(row=4, column=0, sticky="ew")
        self._build_actions(self).grid(row=5, column=0, sticky="ew", pady=(8, 0))

    def _build_header(self, parent) -> tk.Frame:
        bg = _tok("CARD_BG", "#FFFFFF")
        fg = _tok("TEXT", "#111827")
        muted = _tok("TEXT_MUTED", "#6B7280")
        f = tk.Frame(parent, bg=bg)
        f.columnconfigure(0, weight=1)
        tk.Label(
            f, text="ثبت ورود، خروج و گردش کالا",
            bg=bg, fg=fg, font=_tok("FONT_SECTION", ("Tahoma", 12, "bold")),
            anchor="e",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            f, text="کالا و مقدار را انتخاب و به سند اضافه کنید؛ سپس ثبت قطعی کنید.",
            bg=bg, fg=muted, font=_tok("FONT_SMALL", ("Tahoma", 9)),
            anchor="e",
        ).grid(row=1, column=0, sticky="ew", pady=(3, 0))
        return f

    def _build_type_bar(self, parent) -> tk.Frame:
        bg = _tok("BG", "#F9FAFB")
        fg = _tok("TEXT", "#111827")
        f = tk.Frame(
            parent, bg=bg,
            highlightbackground=_tok("CARD_BORDER", "#E5E7EB"),
            highlightthickness=1, padx=12, pady=8,
        )
        f.columnconfigure(0, weight=1)
        tk.Label(
            f, text="نوع گردش:", bg=bg, fg=fg,
            font=_tok("FONT_BOLD", ("Tahoma", 10, "bold")), anchor="e",
        ).grid(row=0, column=1, padx=(10, 0))
        radio_row = tk.Frame(f, bg=bg)
        radio_row.grid(row=0, column=0, sticky="e")
        self.type_var = tk.StringVar(value=next(iter(TYPES), "IN"))
        self._type_radios = []
        for key, label in TYPES.items():
            rb = ttk.Radiobutton(radio_row, text=label, value=key, variable=self.type_var)
            rb.pack(side=tk.RIGHT, padx=(0, 10))
            self._type_radios.append(rb)
        return f

    def _build_workspace(self, parent) -> tk.Frame:
        ws = tk.Frame(parent, bg=_tok("CARD_BG", "#FFFFFF"))
        ws.columnconfigure(0, weight=5, uniform="ws")
        ws.columnconfigure(1, weight=7, uniform="ws")
        ws.rowconfigure(0, weight=1)
        self._build_add_panel(ws).grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._build_cart_panel(ws).grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        return ws

    def _build_add_panel(self, parent) -> tk.Frame:
        bg = _tok("CARD_BG", "#FFFFFF")
        fg = _tok("TEXT", "#111827")
        panel = tk.Frame(parent, bg=bg)
        panel.columnconfigure(0, weight=1)

        tk.Label(
            panel, text="افزودن قلم به سند", bg=bg, fg=fg,
            font=_tok("FONT_BOLD", ("Tahoma", 10, "bold")), anchor="e",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        tk.Label(
            panel, text="کالا *", bg=bg, fg=fg,
            font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e",
        ).grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self.prod_var = tk.StringVar()
        self._combo = ttk.Combobox(
            panel, textvariable=self.prod_var, state="readonly", height=14,
        )
        self._combo.grid(row=2, column=0, sticky="ew", ipady=3, pady=(0, 8))
        self._combo.bind("<<ComboboxSelected>>", self._on_select)

        info_bg = _tok("INFO_BG", "#F0F9FF")
        info_border = _tok("INFO_BORDER", "#BAE6FD")
        self._info_card = tk.Frame(
            panel, bg=info_bg,
            highlightbackground=info_border, highlightthickness=1,
            padx=10, pady=8,
        )
        self._info_card.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self._info_card.columnconfigure(0, weight=1)
        self._info_title = tk.Label(
            self._info_card, text="وضعیت موجودی", bg=info_bg,
            fg=_tok("PRIMARY", "#0EA5E9"),
            font=_tok("FONT_BOLD", ("Tahoma", 10, "bold")), anchor="e",
        )
        self._info_title.grid(row=0, column=0, sticky="ew")
        self._info_label = tk.Label(
            self._info_card, text=self.INFO_EMPTY, bg=info_bg,
            fg=_tok("TEXT_MUTED", "#6B7280"),
            font=_tok("FONT_SMALL", ("Tahoma", 9)),
            anchor="e", justify="right", wraplength=320,
        )
        self._info_label.grid(row=1, column=0, sticky="ew", pady=(3, 0))

        tk.Label(
            panel, text="مقدار *", bg=bg, fg=fg,
            font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e",
        ).grid(row=4, column=0, sticky="ew", pady=(0, 4))
        qty_row = tk.Frame(panel, bg=bg)
        qty_row.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        qty_row.columnconfigure(0, weight=1)
        self.qty_var = tk.StringVar()
        self._qty_entry = ttk.Entry(qty_row, textvariable=self.qty_var, justify="right")
        self._qty_entry.grid(row=0, column=0, sticky="ew", ipady=3)
        self._qty_entry.bind("<Return>", lambda _e: self._add_line())
        self._unit_label = tk.Label(
            qty_row, text="—", bg=bg, fg=_tok("TEXT_MUTED", "#6B7280"),
            font=_tok("FONT_SMALL", ("Tahoma", 9)), width=8, anchor="e",
        )
        self._unit_label.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self._add_btn = ttk.Button(
            panel, text="➕ افزودن به سند", style="Primary.TButton",
            command=self._add_line,
        )
        self._add_btn.grid(row=6, column=0, sticky="ew", ipady=4)
        return panel

    def _build_cart_panel(self, parent) -> tk.Frame:
        bg = _tok("CARD_BG", "#FFFFFF")
        fg = _tok("TEXT", "#111827")
        panel = tk.Frame(parent, bg=bg)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        tk.Label(
            panel, text="اقلام سند", bg=bg, fg=fg,
            font=_tok("FONT_BOLD", ("Tahoma", 10, "bold")), anchor="e",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        tree_container = tk.Frame(panel, bg=bg)
        tree_container.grid(row=1, column=0, sticky="nsew")
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        columns = ("idx", "code", "name", "unit", "qty")
        self._tree = ttk.Treeview(
            tree_container, columns=columns, show="headings",
            height=6, selectmode="browse",
        )
        self._tree.heading("idx", text="#")
        self._tree.heading("code", text="کد")
        self._tree.heading("name", text="کالا")
        self._tree.heading("unit", text="واحد")
        self._tree.heading("qty", text="مقدار")
        self._tree.column("idx", width=40, anchor="center", stretch=False)
        self._tree.column("code", width=90, anchor="center", stretch=False)
        self._tree.column("name", width=200, anchor="e")
        self._tree.column("unit", width=70, anchor="center", stretch=False)
        self._tree.column("qty", width=80, anchor="center", stretch=False)
        self._tree.grid(row=0, column=0, sticky="nsew")
        self._tree.bind("<Delete>", lambda _e: self._remove_selected())
        self._tree.bind("<Double-1>", lambda _e: self._remove_selected())

        scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self._tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=scroll.set)

        summary_row = tk.Frame(panel, bg=bg)
        summary_row.grid(row=2, column=0, sticky="ew", pady=(8, 6))
        summary_row.columnconfigure(0, weight=1)
        self._cart_summary = tk.Label(
            summary_row, text=self.INFO_NO_ITEMS, bg=bg,
            fg=_tok("TEXT_MUTED", "#6B7280"),
            font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e",
        )
        self._cart_summary.grid(row=0, column=0, sticky="ew")

        actions = tk.Frame(panel, bg=bg)
        actions.grid(row=3, column=0, sticky="ew")
        self._remove_btn = ttk.Button(
            actions, text="حذف قلم", style="Ghost.TButton",
            command=self._remove_selected,
        )
        self._remove_btn.pack(side=tk.RIGHT)
        self._clear_cart_btn = ttk.Button(
            actions, text="پاک کردن سند", style="Ghost.TButton",
            command=self._clear_cart,
        )
        self._clear_cart_btn.pack(side=tk.RIGHT, padx=(0, 6))
        return panel

    def _build_metadata(self, parent) -> tk.Frame:
        bg = _tok("CARD_BG", "#FFFFFF")
        fg = _tok("TEXT", "#111827")
        f = tk.Frame(
            parent, bg=bg,
            highlightbackground=_tok("CARD_BORDER", "#E5E7EB"),
            highlightthickness=1, padx=12, pady=10,
        )
        f.columnconfigure(0, weight=1, uniform="meta")
        f.columnconfigure(1, weight=1, uniform="meta")
        f.columnconfigure(2, weight=1, uniform="meta")

        tk.Label(
            f, text="اطلاعات سند", bg=bg, fg=fg,
            font=_tok("FONT_BOLD", ("Tahoma", 10, "bold")), anchor="e",
        ).grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        # Row 1-2: date / party / reference (RTL: date rightmost)
        tk.Label(f, text="تاریخ شمسی *", bg=bg, fg=fg,
                 font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e",
                 ).grid(row=1, column=2, sticky="e", pady=(0, 4))
        self.date_var = tk.StringVar(value=today_jalali())
        self._date_entry = ttk.Entry(f, textvariable=self.date_var, justify="right")
        self._date_entry.grid(row=2, column=2, sticky="ew", padx=(4, 0), ipady=3)
        self._date_entry.bind("<Return>", lambda _e: self._submit())

        tk.Label(f, text="طرف حساب / واحد", bg=bg, fg=fg,
                 font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e",
                 ).grid(row=1, column=1, sticky="e", pady=(0, 4))
        self.party_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.party_var, justify="right").grid(
            row=2, column=1, sticky="ew", padx=4, ipady=3)

        tk.Label(f, text="شماره مرجع", bg=bg, fg=fg,
                 font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e",
                 ).grid(row=1, column=0, sticky="e", pady=(0, 4))
        self.reference_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.reference_var, justify="right").grid(
            row=2, column=0, sticky="ew", padx=(0, 4), ipady=3)

        # Row 3-4: delivered / received
        tk.Label(f, text="تحویل‌دهنده", bg=bg, fg=fg,
                 font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e",
                 ).grid(row=3, column=2, sticky="e", pady=(8, 4))
        self.delivered_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.delivered_var, justify="right").grid(
            row=4, column=2, sticky="ew", padx=(4, 0), ipady=3)

        tk.Label(f, text="تحویل‌گیرنده", bg=bg, fg=fg,
                 font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e",
                 ).grid(row=3, column=1, sticky="e", pady=(8, 4))
        self.received_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.received_var, justify="right").grid(
            row=4, column=1, sticky="ew", padx=4, ipady=3)

        # Row 5-6: note full width
        tk.Label(f, text="توضیحات", bg=bg, fg=fg,
                 font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e",
                 ).grid(row=5, column=0, columnspan=3, sticky="e", pady=(8, 4))
        self.note_var = tk.StringVar()
        self._note_entry = ttk.Entry(f, textvariable=self.note_var, justify="right")
        self._note_entry.grid(row=6, column=0, columnspan=3, sticky="ew", ipady=3)
        self._note_entry.bind("<Return>", lambda _e: self._submit())
        return f

    def _build_status(self, parent) -> tk.Frame:
        bg = _tok("CARD_BG", "#FFFFFF")
        f = tk.Frame(parent, bg=bg)
        f.columnconfigure(0, weight=1)
        self._status_label = tk.Label(
            f, text="", bg=bg, fg=_tok("TEXT_MUTED", "#6B7280"),
            font=_tok("FONT_SMALL", ("Tahoma", 9)),
            anchor="e", justify="right", wraplength=800,
        )
        self._status_label.grid(row=0, column=0, sticky="ew")
        return f

    def _build_actions(self, parent) -> tk.Frame:
        bg = _tok("CARD_BG", "#FFFFFF")
        f = tk.Frame(parent, bg=bg)
        f.columnconfigure(0, weight=1)

        ttk.Button(
            f, text="مدیریت کالاها", style="Ghost.TButton",
            command=self._manage_products,
        ).grid(row=0, column=0, sticky="w")

        self._clear_btn = ttk.Button(
            f, text="پاک کردن فرم", style="Secondary.TButton",
            command=self._clear,
        )
        self._clear_btn.grid(row=0, column=1, padx=6, sticky="e")

        self._submit_btn = ttk.Button(
            f, text="✓ ثبت قطعی سند", style="Primary.TButton",
            command=self._submit,
        )
        self._submit_btn.grid(row=0, column=2, sticky="e")
        return f

    # -------------------------------------------------------------- selection

    def refresh(self, category: Optional[str] = None) -> None:
        self._cat = category
        items = self.ps.combo_items(category)
        current = self.prod_var.get()
        self._combo["values"] = items
        if current and current not in items:
            self.prod_var.set("")
        self._update_info()

    def _current_product(self) -> Optional[Product]:
        code = self.ps.code_from_label(self.prod_var.get())
        return self.ps.get(code) if code else None

    def _on_select(self, _event=None) -> None:
        p = self._current_product()
        if p is None:
            self._show_empty_info()
            return
        self._show_info(p)
        self._unit_label.config(text=p.unit or "—")
        self._qty_entry.focus_set()

    def _update_info(self) -> None:
        p = self._current_product()
        if p is None:
            self._show_empty_info()
        else:
            self._show_info(p)

    def _show_empty_info(self) -> None:
        self._info_label.config(text=self.INFO_EMPTY, fg=_tok("TEXT_MUTED", "#6B7280"))
        self._unit_label.config(text="—")

    def _show_info(self, p: Product) -> None:
        color = (
            _tok("STOCK_CRIT", "#EF4444") if p.is_critical()
            else _tok("STOCK_LOW", "#F59E0B") if p.is_low()
            else _tok("STOCK_OK", "#10B981")
        )
        status = "بحرانی" if p.is_critical() else "کم" if p.is_low() else "مناسب"
        shelf = p.shelf or "—"
        self._info_label.config(
            text=(
                f"موجودی فعلی: {p.stock:g} {p.unit}  •  "
                f"حداقل: {p.min_stock:g}  •  "
                f"قفسه: {shelf}  •  "
                f"وضعیت: {status}"
            ),
            fg=color,
        )

    # ------------------------------------------------------------------- cart

    def _add_line(self) -> None:
        code = self.ps.code_from_label(self.prod_var.get())
        if not code:
            self._set_status("لطفاً یک کالا انتخاب کنید.", "error")
            self._combo.focus_set()
            return
        try:
            qty = parse_positive_qty(self.qty_var.get())
        except ValueError as exc:
            self._set_status(str(exc), "error")
            self._qty_entry.focus_set()
            return
        product = self.ps.get(code)
        if product is None:
            self._set_status("کالای انتخاب‌شده دیگر در فهرست وجود ندارد.", "error")
            self.refresh()
            return
        current_type = self.type_var.get()
        if self._items and self._items[0]["type"] != current_type:
            self._set_status(
                "نوع سند را نمی‌توان پس از افزودن قلم تغییر داد. ابتدا سند را پاک کنید.",
                "error",
            )
            return
        self._items.append({
            "code": code, "name": product.name, "unit": product.unit,
            "type": current_type, "qty": qty,
        })
        self._refresh_cart()
        self._reset_add_fields()
        self._set_status(
            f"«{product.name}» به مقدار {qty:g} {product.unit} به سند اضافه شد.",
            "ok",
        )
        self._combo.focus_set()

    def _remove_selected(self) -> None:
        selection = self._tree.selection()
        if not selection:
            self._set_status("ابتدا یک قلم از سند را انتخاب کنید.", "warn")
            return
        idx = int(selection[0])
        if 0 <= idx < len(self._items):
            removed = self._items.pop(idx)
            self._refresh_cart()
            self._set_status(f"قلم «{removed['name']}» از سند حذف شد.", "info")

    def _clear_cart(self) -> None:
        if not self._items:
            return
        if not messagebox.askyesno(
            "پاک کردن سند",
            f"همهٔ {len(self._items)} قلم سند پاک شود؟",
            parent=self.winfo_toplevel(),
        ):
            return
        self._items.clear()
        self._refresh_cart()
        self._set_status("سند پاک شد.", "info")

    def _refresh_cart(self) -> None:
        for item_id in self._tree.get_children():
            self._tree.delete(item_id)
        for index, item in enumerate(self._items):
            self._tree.insert(
                "", "end", iid=str(index),
                values=(
                    f"{index + 1}",
                    item["code"],
                    item["name"],
                    item["unit"],
                    f"{item['qty']:g}",
                ),
            )
        if not self._items:
            self._cart_summary.config(text=self.INFO_NO_ITEMS)
        else:
            by_unit: dict[str, float] = {}
            for item in self._items:
                by_unit[item["unit"]] = by_unit.get(item["unit"], 0) + item["qty"]
            parts = [f"{len(self._items)} قلم"]
            parts.extend(f"{total:g} {unit}" for unit, total in by_unit.items())
            self._cart_summary.config(text="  •  ".join(parts))

        state = ["disabled"] if self._items else ["!disabled"]
        for rb in self._type_radios:
            rb.state(state)
        for btn in (self._remove_btn, self._clear_cart_btn):
            btn.state(["!disabled"] if self._items else ["disabled"])

    def _reset_add_fields(self) -> None:
        self.prod_var.set("")
        self.qty_var.set("")
        self._show_empty_info()

    # ----------------------------------------------------------------- submit

    def _submit(self) -> None:
        if self._submitting:
            return
        if not self._items:
            self._set_status(
                "برای ثبت سند، دست‌کم یک قلم کالا اضافه کنید.", "error")
            self._combo.focus_set()
            return
        try:
            tx_date = validate_transaction_date(from_jalali(self.date_var.get()))
        except ValueError as exc:
            self._set_status(str(exc), "error")
            self._date_entry.focus_set()
            return

        self._submitting = True
        self._submit_btn.state(["disabled"])
        self._set_status("در حال ثبت سند…", "info")
        try:
            saved, warnings, document_no = self.ts.add_document(
                list(self._items),
                date_str=tx_date,
                note=self.note_var.get().strip(),
                party_name=self.party_var.get().strip(),
                delivered_by=self.delivered_var.get().strip(),
                received_by=self.received_var.get().strip(),
                reference_no=self.reference_var.get().strip(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Warehouse document post failed")
            self._submitting = False
            self._submit_btn.state(["!disabled"])
            self._set_status(f"ثبت سند ناموفق بود: {exc}", "error")
            messagebox.showerror(
                "خطا در ثبت سند", str(exc), parent=self.winfo_toplevel())
            return

        self._submitting = False
        self._submit_btn.state(["!disabled"])

        summary = f"سند {document_no} با {len(saved)} قلم ثبت قطعی شد."
        if warnings:
            messagebox.showwarning(
                "سند با هشدار ثبت شد",
                summary + "\n\n" + "\n".join(warnings),
                parent=self.winfo_toplevel(),
            )
        else:
            messagebox.showinfo(
                "ثبت سند", summary, parent=self.winfo_toplevel())

        self._clear(preserve_type=True, skip_confirm=True)
        self._set_status(summary, "ok")
        if self.on_ok is not None:
            try:
                self.on_ok()
            except Exception:
                logger.exception("on_ok callback failed")

    def _clear(
        self, preserve_type: bool = False, skip_confirm: bool = False
    ) -> None:
        if self._items and not skip_confirm:
            if not messagebox.askyesno(
                "پاک کردن فرم",
                "فرم شامل اقلام ثبت‌نشده است. همه پاک شود؟",
                parent=self.winfo_toplevel(),
            ):
                return
        self._reset_add_fields()
        self._items.clear()
        self._refresh_cart()
        self.party_var.set("")
        self.reference_var.set("")
        self.delivered_var.set("")
        self.received_var.set("")
        self.note_var.set("")
        self.date_var.set(today_jalali())
        if not preserve_type:
            self.type_var.set(next(iter(TYPES), "IN"))
        if not skip_confirm:
            self._set_status("", "info")
        self._combo.focus_set()

    # --------------------------------------------------------------- helpers

    def _set_status(self, text: str, kind: str = "info") -> None:
        colors = {
            "info": _tok("TEXT_MUTED", "#6B7280"),
            "ok": _tok("STOCK_OK", "#10B981"),
            "warn": _tok("STOCK_LOW", "#F59E0B"),
            "error": _tok("STOCK_CRIT", "#EF4444"),
        }
        self._status_label.config(text=text, fg=colors.get(kind, colors["info"]))
        if self._status_after_id is not None:
            try:
                self.after_cancel(self._status_after_id)
            except tk.TclError:
                pass
            self._status_after_id = None
        if kind == "ok" and text:
            def _clear_status():
                try:
                    self._set_status("", "info")
                except tk.TclError:
                    pass
            self._status_after_id = self.after(self.STATUS_CLEAR_MS, _clear_status)

    def _manage_products(self) -> None:
        if self.on_manage_products is None:
            messagebox.showinfo(
                "فهرست کالاها",
                "دسترسی به فهرست کالا در این فرم پیکربندی نشده است.",
                parent=self.winfo_toplevel(),
            )
            return
        self.on_manage_products()
        self.refresh()
