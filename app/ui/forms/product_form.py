# -*- coding: utf-8 -*-
"""فرم افزودن/ویرایش کالا — چیدمان کارتی با هدر ثابت شامل دکمه‌ها."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from app.config import CATEGORIES, UNITS
from app.models.product import Product
from app.services.product_service import ProductService
from app.ui import theme as T

logger = logging.getLogger(__name__)


def _tok(name: str, default):
    """دریافت توکن تم با مقدار پیش‌فرض در صورت نبود."""
    return getattr(T, name, default)


class ProductForm(tk.Toplevel):
    """دیالوگ افزودن یا ویرایش کالا."""

    # اندازهٔ ترجیحی؛ اگر محتوا بزرگ‌تر باشد، بزرگ‌تر می‌شود.
    PREFERRED_WIDTH = 640
    PREFERRED_HEIGHT = 600
    ABSOLUTE_MIN_WIDTH = 480
    ABSOLUTE_MIN_HEIGHT = 400
    STATUS_CLEAR_MS = 4000

    def __init__(
        self,
        master: tk.Misc,
        service: ProductService,
        product: Optional[Product] = None,
        on_save: Optional[Callable[[], None]] = None,
        initial_user_code: str = "",
    ) -> None:
        super().__init__(master)
        logger.info("ProductForm opening (product=%r)", product)

        self.service = service
        self.product = product
        self.on_save = on_save
        self._saving = False
        self._status_after_id: Optional[str] = None

        # متغیرها قبل از ساخت ویجت‌ها
        self.user_code_var = tk.StringVar(value=initial_user_code)
        self.name_var = tk.StringVar()
        self.unit_var = tk.StringVar(value="عدد")
        self.min_var = tk.StringVar(value="0")
        self.cat_var = tk.StringVar(value="مصرفی")
        self.shelf_var = tk.StringVar()

        # تنظیمات پایه پنجره
        self.title("ویرایش کالا" if self.product else "کالای جدید")
        self.configure(bg=_tok("BG", "#F3F4F6"))

        # ۱) ساخت فرم — قبل از هر geometry
        self._build_form()
        if product is not None:
            self._load_product(product)
        self._bind_shortcuts()

        # ۲) اندازه‌گیری و تنظیم اندازه بر اساس محتوای واقعی
        self._fit_to_content(master)

        # ۳) نمایش و فوکوس
        self.lift()
        self.grab_set()
        self._focus_initial()

    # ------------------------------------------------------------ window

    def _fit_to_content(self, master: tk.Misc) -> None:
        """تعیین اندازه و مرکز پس از ساخت ویجت‌ها.

        نکته: update_idletasks() باعث می‌شود winfo_reqwidth/height
        مقادیر واقعی محتوا را برگردانند.
        """
        self.update_idletasks()

        req_w = self.winfo_reqwidth()
        req_h = self.winfo_reqheight()
        sw = max(self.winfo_screenwidth(), 1)
        sh = max(self.winfo_screenheight(), 1)

        # حداکثر اندازه: صفحه منها حاشیه
        max_w = max(sw - 80, self.ABSOLUTE_MIN_WIDTH)
        max_h = max(sh - 140, self.ABSOLUTE_MIN_HEIGHT)

        # اندازهٔ اولیه: بزرگ‌تر از ترجیحی و نیاز محتوا، ولی محدود به صفحه
        w = min(max(req_w, self.PREFERRED_WIDTH), max_w)
        h = min(max(req_h, self.PREFERRED_HEIGHT), max_h)

        # مرکز کردن
        try:
            mx = master.winfo_rootx()
            my = master.winfo_rooty()
            mw = master.winfo_width()
            mh = master.winfo_height()
        except tk.TclError:
            mx = my = mw = mh = 0

        if mw > 1 and mh > 1:
            x = mx + (mw - w) // 2
            y = my + (mh - h) // 2
        else:
            x = (sw - w) // 2
            y = (sh - h) // 2

        x = max(0, min(x, max(sw - w, 0)))
        y = max(0, min(y, max(sh - h, 0)))

        self.geometry(f"{w}x{h}+{x}+{y}")
        self.resizable(True, True)
        self.minsize(
            min(req_w, max_w) if req_w > 0 else self.ABSOLUTE_MIN_WIDTH,
            min(req_h, max_h) if req_h > 0 else self.ABSOLUTE_MIN_HEIGHT,
        )

        logger.info(
            "ProductForm geometry: req=%dx%d, set=%dx%d, screen=%dx%d",
            req_w, req_h, w, h, sw, sh,
        )

    def _bind_shortcuts(self) -> None:
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Control-s>", lambda _e: self._save())
        self.bind("<Control-S>", lambda _e: self._save())

    def _focus_initial(self) -> None:
        target = (
            self._name_entry
            if self.user_code_var.get().strip()
            else self._code_entry
        )
        try:
            target.focus_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------ layout

    def _build_form(self) -> None:
        """ریشه با grid: هدر ثابت (ردیف ۰) + جداکننده (ردیف ۱) + محتوا (ردیف ۲)."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)   # header bar — ارتفاع ثابت، هرگز فشرده نمی‌شود
        self.rowconfigure(1, weight=0)   # separator
        self.rowconfigure(2, weight=1)   # content — تنها بخش کشسان

        # ردیف ۰: هدر شامل عنوان + وضعیت + دکمه‌ها
        self._build_header_bar().grid(
            row=0, column=0, sticky="ew", padx=16, pady=(12, 10)
        )

        # ردیف ۱: جداکننده
        ttk.Separator(self, orient="horizontal").grid(
            row=1, column=0, sticky="ew"
        )

        # ردیف ۲: محتوا
        content = ttk.Frame(self, padding=(16, 12, 16, 12))
        content.grid(row=2, column=0, sticky="nsew")

        self._build_identity_section(content).pack(fill=tk.X, pady=(0, 10))
        self._build_classification_section(content).pack(fill=tk.X, pady=(0, 10))
        self._build_inventory_section(content).pack(fill=tk.X)

    def _build_header_bar(self) -> tk.Frame:
        """هدر با عنوان (راست)، وضعیت (وسط)، دکمه‌ها (چپ). همیشه در دید."""
        bg = _tok("BG", "#F3F4F6")
        bar = tk.Frame(self, bg=bg)
        bar.columnconfigure(1, weight=1)   # ستون وسط کشسان است

        # ستون ۰: دکمه‌ها (سمت چپ)
        btns = tk.Frame(bar, bg=bg)
        btns.grid(row=0, column=0, sticky="w")
        self._submit_btn = ttk.Button(
            btns, text="✓  ذخیره", style="Primary.TButton",
            command=self._save, width=12,
        )
        self._submit_btn.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            btns, text="انصراف", style="Secondary.TButton",
            command=self.destroy, width=10,
        ).pack(side=tk.LEFT)

        # ستون ۱: نوار وضعیت (وسط — کشسان)
        self._status_label = tk.Label(
            bar, text="",
            bg=bg, fg=_tok("TEXT_MUTED", "#6B7280"),
            font=_tok("FONT_SMALL", ("Tahoma", 9)),
            anchor="e", justify="right", wraplength=300,
        )
        self._status_label.grid(row=0, column=1, sticky="ew", padx=(12, 12))

        # ستون ۲: عنوان (سمت راست، RTL)
        title_frame = tk.Frame(bar, bg=bg)
        title_frame.grid(row=0, column=2, sticky="e")
        if self.product is not None:
            title_text = f"ویرایش «{self.product.name}»"
        else:
            title_text = "کالای جدید"
        tk.Label(
            title_frame, text=title_text, bg=bg, fg=_tok("TEXT", "#111827"),
            font=_tok("FONT_SECTION", ("Tahoma", 12, "bold")), anchor="e",
        ).pack(anchor="e")
        tk.Label(
            title_frame, text="مشخصات کالا را وارد کنید.",
            bg=bg, fg=_tok("TEXT_MUTED", "#6B7280"),
            font=_tok("FONT_SMALL", ("Tahoma", 9)), anchor="e",
        ).pack(anchor="e")

        return bar

    def _build_identity_section(self, parent) -> tk.Frame:
        bg = _tok("CARD_BG", "#FFFFFF")
        section = tk.Frame(
            parent, bg=bg,
            highlightbackground=_tok("CARD_BORDER", "#E5E7EB"),
            highlightthickness=1, padx=14, pady=10,
        )
        section.columnconfigure(1, weight=1)

        tk.Label(
            section, text="شناسه کالا", bg=bg, fg=_tok("TEXT", "#111827"),
            font=_tok("FONT_BOLD", ("Tahoma", 10, "bold")), anchor="e",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self._add_label(section, 1, "کد کالا *")
        self._code_entry = ttk.Entry(section, textvariable=self.user_code_var)
        self._code_entry.grid(row=1, column=1, sticky="ew", ipady=3, pady=(0, 6))
        self._code_entry.bind("<Return>", lambda _e: self._name_entry.focus_set())

        self._add_label(section, 2, "نام کالا *")
        self._name_entry = ttk.Entry(section, textvariable=self.name_var)
        self._name_entry.grid(row=2, column=1, sticky="ew", ipady=3, pady=(0, 4))
        self._name_entry.bind("<Return>", lambda _e: self._save())

        return section

    def _build_classification_section(self, parent) -> tk.Frame:
        bg = _tok("CARD_BG", "#FFFFFF")
        section = tk.Frame(
            parent, bg=bg,
            highlightbackground=_tok("CARD_BORDER", "#E5E7EB"),
            highlightthickness=1, padx=14, pady=10,
        )
        section.columnconfigure(1, weight=1)

        tk.Label(
            section, text="واحد و دسته‌بندی", bg=bg, fg=_tok("TEXT", "#111827"),
            font=_tok("FONT_BOLD", ("Tahoma", 10, "bold")), anchor="e",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self._add_label(section, 1, "واحد *")
        ttk.Combobox(
            section, textvariable=self.unit_var, values=list(UNITS),
        ).grid(row=1, column=1, sticky="ew", ipady=3, pady=(0, 6))

        self._add_label(section, 2, "دسته")
        ttk.Combobox(
            section, textvariable=self.cat_var, values=list(CATEGORIES),
            state="readonly",
        ).grid(row=2, column=1, sticky="ew", ipady=3, pady=(0, 6))

        self._add_label(section, 3, "قفسه")
        shelf_entry = ttk.Entry(section, textvariable=self.shelf_var)
        shelf_entry.grid(row=3, column=1, sticky="ew", ipady=3, pady=(0, 4))
        shelf_entry.bind("<Return>", lambda _e: self._save())

        return section

    def _build_inventory_section(self, parent) -> tk.Frame:
        bg = _tok("CARD_BG", "#FFFFFF")
        section = tk.Frame(
            parent, bg=bg,
            highlightbackground=_tok("CARD_BORDER", "#E5E7EB"),
            highlightthickness=1, padx=14, pady=10,
        )
        section.columnconfigure(1, weight=1)

        tk.Label(
            section, text="موجودی", bg=bg, fg=_tok("TEXT", "#111827"),
            font=_tok("FONT_BOLD", ("Tahoma", 10, "bold")), anchor="e",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self._add_label(section, 1, "حداقل موجودی")
        min_entry = ttk.Entry(section, textvariable=self.min_var)
        min_entry.grid(row=1, column=1, sticky="ew", ipady=3, pady=(0, 4))
        min_entry.bind("<Return>", lambda _e: self._save())

        tk.Label(
            section,
            text="اختیاری — آستانهٔ هشدار خودکار کمبود موجودی (پیش‌فرض: ۰).",
            bg=bg, fg=_tok("TEXT_MUTED", "#6B7280"),
            font=_tok("FONT_SMALL", ("Tahoma", 9)),
            anchor="e", justify="right",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 0))

        return section

    def _add_label(self, parent: tk.Frame, row: int, text: str) -> tk.Label:
        bg = parent.cget("bg")
        label = tk.Label(
            parent, text=text, bg=bg, fg=_tok("TEXT", "#111827"),
            font=_tok("FONT", ("Tahoma", 10)), anchor="e",
        )
        label.grid(row=row, column=0, sticky="e", padx=(0, 10), pady=(0, 6))
        return label

    # ------------------------------------------------------------ load

    def _load_product(self, product: Product) -> None:
        self.user_code_var.set(product.user_code or product.code)
        self.name_var.set(product.name)
        self.unit_var.set(product.unit)
        self.min_var.set(self._fmt(product.min_stock))
        self.cat_var.set(product.category)
        self.shelf_var.set(product.shelf)

    @staticmethod
    def _fmt(value: float) -> str:
        try:
            if float(value).is_integer():
                return str(int(value))
        except (TypeError, ValueError):
            pass
        return str(value)

    @staticmethod
    def _coerce_min_stock(raw: str) -> float:
        text = (raw or "").strip() or "0"
        if text == "0":
            return 0.0

        from app.services.transaction_service import parse_positive_qty

        try:
            return parse_positive_qty(text)
        except ValueError:
            pass

        try:
            value = float(text.replace(",", "."))
        except ValueError as exc:
            raise ValueError("حداقل موجودی باید عدد غیرمنفی باشد.") from exc
        if value < 0:
            raise ValueError("حداقل موجودی باید عدد غیرمنفی باشد.")
        return value

    # ------------------------------------------------------------ save

    def _save(self) -> None:
        if self._saving:
            return
        name = self.name_var.get().strip()
        if not name:
            self._set_status("نام کالا را وارد کنید.", "error")
            self._name_entry.focus_set()
            return

        user_code = self.user_code_var.get().strip()
        if not user_code:
            self._set_status("کد کالا را وارد کنید.", "error")
            self._code_entry.focus_set()
            return

        try:
            min_stock = self._coerce_min_stock(self.min_var.get())
        except ValueError as exc:
            self._set_status(str(exc), "error")
            return

        unit = self.unit_var.get().strip() or "عدد"
        category = self.cat_var.get()
        shelf = self.shelf_var.get().strip()

        current_code = self.product.code if self.product is not None else None
        warnings = self.service.duplicate_warnings(name, user_code, current_code)
        if warnings and not messagebox.askyesno(
            "هشدار تکراری بودن کالا",
            "\n".join(warnings) + "\n\nبا وجود هشدار، ثبت را ادامه می‌دهید؟",
            parent=self,
        ):
            return

        self._saving = True
        self._submit_btn.state(["disabled"])
        self._set_status("در حال ذخیره…", "info")
        try:
            if self.product is not None:
                self.service.update(
                    self.product.code, name, unit, min_stock,
                    category, shelf, user_code,
                )
                message = "کالا ویرایش شد."
            else:
                created = self.service.add(
                    name, unit, min_stock, category, shelf, user_code
                )
                message = f"کالا با کد «{created.user_code}» ثبت شد."
        except Exception as exc:  # noqa: BLE001
            logger.exception("Saving product failed")
            self._saving = False
            self._submit_btn.state(["!disabled"])
            self._set_status(f"ذخیره ناموفق بود: {exc}", "error")
            messagebox.showerror("خطا", str(exc), parent=self)
            return

        self._saving = False
        self._submit_btn.state(["!disabled"])
        messagebox.showinfo("موفق", message, parent=self)
        try:
            if self.on_save is not None:
                self.on_save()
        except Exception:
            logger.exception("on_save callback failed")
        finally:
            self.destroy()

    # ------------------------------------------------------------ status

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
