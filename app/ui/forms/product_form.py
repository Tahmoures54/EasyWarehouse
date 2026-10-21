# -*- coding: utf-8 -*-
"""فرم بازطراحی‌شدهٔ افزودن و ویرایش کالا با چیدمان راست‌به‌چپ و کارت‌های واضح."""

from __future__ import annotations

import logging
import math
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from app.config import CATEGORIES, UNITS
from app.models.product import Product
from app.services.product_service import ProductService
from app.ui import theme as T

logger = logging.getLogger(__name__)


def _tok(name: str, default):
    return getattr(T, name, default)


class ProductForm(tk.Toplevel):
    """پنجرهٔ مستقل و بخش‌بندی‌شده برای ثبت یا ویرایش مشخصات کالا."""

    PREFERRED_WIDTH = 760
    PREFERRED_HEIGHT = 1000
    MIN_WIDTH = 620
    MIN_HEIGHT = 800
    STATUS_CLEAR_MS = 4500

    def __init__(
        self,
        master: tk.Misc,
        service: ProductService,
        product: Optional[Product] = None,
        on_save: Optional[Callable[[], None]] = None,
        initial_user_code: str = "",
    ) -> None:
        super().__init__(master)
        self.service = service
        self.product = product
        self.on_save = on_save
        self._saving = False
        self._status_after_id: Optional[str] = None

        self.user_code_var = tk.StringVar(value=initial_user_code)
        self.name_var = tk.StringVar()
        self.unit_var = tk.StringVar(value="عدد")
        self.min_var = tk.StringVar(value="0")
        self.cat_var = tk.StringVar(value="مصرفی")
        self.shelf_var = tk.StringVar()

        self.title("ویرایش کالا" if product else "ثبت کالای جدید")
        self.configure(bg=_tok("BG", "#F3F6FB"))
        self.transient(master)

        self._build_form()
        if product is not None:
            self._load_product(product)
        self._bind_shortcuts()
        self._fit_to_content(master)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.lift()
        self.grab_set()
        self._focus_initial()

    # ---------------------------------------------------------------- window

    def _fit_to_content(self, master: tk.Misc) -> None:
        self.update_idletasks()
        sw, sh = max(self.winfo_screenwidth(), 1), max(self.winfo_screenheight(), 1)
        # Use a taller default so the footer buttons remain visible, while still
        # keeping the window inside the usable screen area on smaller displays.
        max_w = max(sw - 64, 420)
        max_h = max(sh - 40, 420)
        w = min(max(self.winfo_reqwidth(), self.PREFERRED_WIDTH), max_w)
        h = min(max(self.winfo_reqheight(), self.PREFERRED_HEIGHT), max_h)

        try:
            mx, my = master.winfo_rootx(), master.winfo_rooty()
            mw, mh = master.winfo_width(), master.winfo_height()
        except tk.TclError:
            mx = my = mw = mh = 0
        if mw > 1 and mh > 1:
            x, y = mx + (mw - w) // 2, my + (mh - h) // 2
        else:
            x, y = (sw - w) // 2, (sh - h) // 2
        x = max(0, min(x, max(sw - w, 0)))
        y = max(0, min(y, max(sh - h, 0)))
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(self.MIN_WIDTH, max_w), min(self.MIN_HEIGHT, max_h))
        self.resizable(True, True)

    def _bind_shortcuts(self) -> None:
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Control-s>", lambda _event: self._save())
        self.bind("<Control-S>", lambda _event: self._save())

    def _focus_initial(self) -> None:
        target = self._name_entry if self.user_code_var.get().strip() else self._code_entry
        try:
            target.focus_set()
            if target is self._code_entry:
                target.selection_range(0, tk.END)
        except tk.TclError:
            pass

    # ---------------------------------------------------------------- layout

    def _build_form(self) -> None:
        bg = _tok("BG", "#F3F6FB")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg=_tok("HEADER_BG", "#102A43"), padx=24, pady=18)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title = "ویرایش مشخصات کالا" if self.product else "ثبت کالای جدید"
        subtitle = (
            f"کد داخلی: {self.product.code}  •  تغییر اطلاعات پایهٔ کالا"
            if self.product else "کالای جدید را یک‌بار تعریف کنید تا در اسناد انبار قابل انتخاب باشد."
        )
        tk.Label(
            header, text=title, bg=_tok("HEADER_BG", "#102A43"),
            fg=_tok("HEADER_FG", "#FFFFFF"),
            font=_tok("FONT_HEADER", ("Tahoma", 18, "bold")), anchor="e",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            header, text=subtitle, bg=_tok("HEADER_BG", "#102A43"),
            fg=_tok("HEADER_MUTED", "#C7D8E8"),
            font=_tok("FONT", ("Tahoma", 10)), anchor="e", justify="right",
            wraplength=680,
        ).grid(row=1, column=0, sticky="ew", pady=(5, 0))

        body = tk.Frame(self, bg=bg, padx=22, pady=18)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1, uniform="form")
        body.columnconfigure(1, weight=1, uniform="form")

        self._build_identity_card(body).grid(
            row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12)
        )
        self._build_classification_card(body).grid(
            row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 12)
        )
        self._build_inventory_card(body).grid(
            row=1, column=0, columnspan=2, sticky="ew"
        )

        footer = tk.Frame(self, bg=_tok("CARD_BG", "#FFFFFF"), padx=22, pady=12)
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(1, weight=1)
        ttk.Button(
            footer, text="✓  ذخیرهٔ کالا", style="Primary.TButton",
            command=self._save, width=16,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._submit_btn = footer.winfo_children()[0]
        ttk.Button(
            footer, text="انصراف", style="Secondary.TButton",
            command=self.destroy, width=12,
        ).grid(row=0, column=1, sticky="w")

        self._status_label = tk.Label(
            footer, text="Ctrl+S برای ذخیره",
            bg=_tok("CARD_BG", "#FFFFFF"),
            fg=_tok("TEXT_MUTED", "#60758B"),
            font=_tok("FONT_SMALL", ("Tahoma", 9)),
            anchor="e", justify="right",
        )
        self._status_label.grid(row=0, column=2, sticky="e", padx=(12, 0))

        ttk.Separator(self, orient="horizontal").grid(row=3, column=0, sticky="ew")

    def _card(self, parent: tk.Misc, title: str, eyebrow: str) -> tk.Frame:
        card = tk.Frame(
            parent, bg=_tok("CARD_BG", "#FFFFFF"),
            highlightbackground=_tok("CARD_BORDER", "#D9E2EF"),
            highlightthickness=1, padx=16, pady=14,
        )
        card.columnconfigure(0, weight=1)
        top = tk.Frame(card, bg=_tok("CARD_BG", "#FFFFFF"))
        top.grid(row=0, column=0, sticky="ew", pady=(0, 13))
        top.columnconfigure(0, weight=1)
        tk.Label(
            top, text=title, bg=_tok("CARD_BG", "#FFFFFF"),
            fg=_tok("TEXT", "#172B4D"),
            font=_tok("FONT_SECTION", ("Tahoma", 12, "bold")), anchor="e",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            top, text=eyebrow, bg=_tok("CARD_BG", "#FFFFFF"),
            fg=_tok("PRIMARY", "#087F8C"),
            font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e",
        ).grid(row=1, column=0, sticky="ew", pady=(3, 0))
        return card

    def _field_label(self, parent: tk.Misc, row: int, text: str) -> None:
        tk.Label(
            parent, text=text, bg=_tok("CARD_BG", "#FFFFFF"),
            fg=_tok("TEXT", "#172B4D"),
            font=_tok("FONT_BOLD", ("Tahoma", 10, "bold")), anchor="e",
        ).grid(row=row, column=0, sticky="ew", pady=(0, 5))

    def _build_identity_card(self, parent: tk.Misc) -> tk.Frame:
        card = self._card(parent, "مشخصات اصلی", "شناسه و نام قابل جست‌وجو")
        self._field_label(card, 1, "کد کالا *")
        self._code_entry = ttk.Entry(card, textvariable=self.user_code_var, justify="right")
        self._code_entry.grid(row=2, column=0, sticky="ew", ipady=4, pady=(0, 11))
        self._code_entry.bind("<Return>", lambda _event: self._name_entry.focus_set())

        self._field_label(card, 3, "نام کالا *")
        self._name_entry = ttk.Entry(card, textvariable=self.name_var, justify="right")
        self._name_entry.grid(row=4, column=0, sticky="ew", ipady=4)
        self._name_entry.bind("<Return>", lambda _event: self._save())
        tk.Label(
            card, text="ستاره (*) یعنی تکمیل این فیلد الزامی است.",
            bg=_tok("CARD_BG", "#FFFFFF"), fg=_tok("TEXT_MUTED", "#60758B"),
            font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e", justify="right",
        ).grid(row=5, column=0, sticky="ew", pady=(10, 0))
        return card

    def _build_classification_card(self, parent: tk.Misc) -> tk.Frame:
        card = self._card(parent, "دسته‌بندی و محل", "برای گزارش‌گیری و یافتن سریع‌تر")
        self._field_label(card, 1, "واحد شمارش *")
        self._unit_combo = ttk.Combobox(
            card, textvariable=self.unit_var, values=list(UNITS), state="readonly",
            justify="right",
        )
        self._unit_combo.grid(row=2, column=0, sticky="ew", ipady=3, pady=(0, 11))

        self._field_label(card, 3, "دستهٔ کالا")
        self._category_combo = ttk.Combobox(
            card, textvariable=self.cat_var, values=list(CATEGORIES), state="readonly",
            justify="right",
        )
        self._category_combo.grid(row=4, column=0, sticky="ew", ipady=3, pady=(0, 11))

        self._field_label(card, 5, "قفسه / محل نگهداری")
        self._shelf_entry = ttk.Entry(card, textvariable=self.shelf_var, justify="right")
        self._shelf_entry.grid(row=6, column=0, sticky="ew", ipady=4)
        self._shelf_entry.bind("<Return>", lambda _event: self._save())
        return card

    def _build_inventory_card(self, parent: tk.Misc) -> tk.Frame:
        card = self._card(parent, "کنترل موجودی", "تنظیم هشدار کمبود")
        card.columnconfigure(0, weight=1)
        self._field_label(card, 1, "حداقل موجودی برای هشدار")
        self._min_entry = ttk.Entry(card, textvariable=self.min_var, justify="right", width=18)
        self._min_entry.grid(row=2, column=0, sticky="ew", ipady=4)
        tk.Label(
            card,
            text="وقتی موجودی به کمتر از این مقدار برسد، کالا در فهرست هشدار کمبود نمایش داده می‌شود. مقدار ۰ یعنی بدون آستانهٔ هشدار.",
            bg=_tok("CARD_BG", "#FFFFFF"), fg=_tok("TEXT_MUTED", "#60758B"),
            font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e", justify="right",
            wraplength=680,
        ).grid(row=3, column=0, sticky="ew", pady=(7, 0))
        self._min_entry.bind("<Return>", lambda _event: self._save())
        return card

    # ---------------------------------------------------------------- data

    def _load_product(self, product: Product) -> None:
        self.user_code_var.set(product.user_code or product.code)
        self.name_var.set(product.name)
        self.unit_var.set(product.unit if product.unit in UNITS else "عدد")
        self.min_var.set(self._fmt(product.min_stock))
        self.cat_var.set(product.category if product.category in CATEGORIES else "عمومی")
        self.shelf_var.set(product.shelf)

    @staticmethod
    def _fmt(value: float) -> str:
        try:
            number = float(value)
            return str(int(number)) if number.is_integer() else str(number)
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _coerce_min_stock(raw: str) -> float:
        value_text = (raw or "").strip().replace(",", ".") or "0"
        try:
            value = float(value_text)
        except ValueError as exc:
            raise ValueError("حداقل موجودی باید عددی معتبر و غیرمنفی باشد.") from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError("حداقل موجودی باید عددی معتبر و غیرمنفی باشد.")
        return value

    # ---------------------------------------------------------------- save

    def _save(self) -> None:
        if self._saving:
            return
        name = self.name_var.get().strip()
        user_code = self.user_code_var.get().strip()
        if not user_code:
            self._set_status("کد کالا را وارد کنید.", "error")
            self._code_entry.focus_set()
            return
        if not name:
            self._set_status("نام کالا را وارد کنید.", "error")
            self._name_entry.focus_set()
            return

        try:
            min_stock = self._coerce_min_stock(self.min_var.get())
        except ValueError as exc:
            self._set_status(str(exc), "error")
            self._min_entry.focus_set()
            return

        unit = self.unit_var.get().strip() or "عدد"
        category = self.cat_var.get().strip() or "عمومی"
        shelf = self.shelf_var.get().strip()
        current_code = self.product.code if self.product is not None else None

        try:
            warnings = self.service.duplicate_warnings(name, user_code, current_code)
        except Exception:
            logger.exception("Duplicate product check failed")
            self._set_status("بررسی تکراری بودن کالا انجام نشد؛ دوباره تلاش کنید.", "error")
            return
        if warnings and not messagebox.askyesno(
            "بررسی کالای تکراری",
            "\n".join(warnings) + "\n\nبا وجود این هشدارها ثبت را ادامه می‌دهید؟",
            parent=self,
        ):
            return

        self._saving = True
        self._submit_btn.state(["disabled"])
        self._set_status("در حال ذخیرهٔ اطلاعات…", "info")
        try:
            if self.product is not None:
                self.service.update(
                    self.product.code, name, unit, min_stock, category, shelf, user_code
                )
                message = "مشخصات کالا با موفقیت ویرایش شد."
            else:
                created = self.service.add(name, unit, min_stock, category, shelf, user_code)
                message = f"کالای «{created.name}» با کد «{created.user_code}» ثبت شد."
        except Exception as exc:  # noqa: BLE001
            logger.exception("Saving product failed")
            self._saving = False
            self._submit_btn.state(["!disabled"])
            self._set_status(f"ذخیره انجام نشد: {exc}", "error")
            messagebox.showerror("ذخیره ناموفق", str(exc), parent=self)
            return

        self._saving = False
        self._submit_btn.state(["!disabled"])
        messagebox.showinfo("عملیات موفق", message, parent=self)
        try:
            if self.on_save is not None:
                self.on_save()
        except Exception:
            logger.exception("on_save callback failed")
        finally:
            self.destroy()

    # ---------------------------------------------------------------- status

    def _set_status(self, text: str, kind: str = "info") -> None:
        colors = {
            "info": _tok("TEXT_MUTED", "#60758B"),
            "ok": _tok("STOCK_OK", "#15803D"),
            "warn": _tok("STOCK_LOW", "#D97706"),
            "error": _tok("STOCK_CRIT", "#DC2626"),
        }
        try:
            self._status_label.config(text=text, fg=colors.get(kind, colors["info"]))
        except tk.TclError:
            return
        if self._status_after_id is not None:
            try:
                self.after_cancel(self._status_after_id)
            except tk.TclError:
                pass
            self._status_after_id = None
        if kind == "ok" and text:
            self._status_after_id = self.after(
                self.STATUS_CLEAR_MS, lambda: self._set_status("", "info")
            )

    def destroy(self) -> None:
        if self._status_after_id is not None:
            try:
                self.after_cancel(self._status_after_id)
            except (tk.TclError, AttributeError):
                pass
            self._status_after_id = None
        try:
            super().destroy()
        except tk.TclError:
            pass
