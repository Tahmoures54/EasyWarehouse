# -*- coding: utf-8 -*-
"""فرم افزودن/ویرایش کالا."""

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


class ProductForm(tk.Toplevel):
    """دیالوگ افزودن یا ویرایش کالا."""

    WIDTH = 520
    HEIGHT = 500
    MIN_WIDTH = 460
    MIN_HEIGHT = 390

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

        # --- متغیرها ابتدا ساخته می‌شوند تا _save هرگز به متغیر نبوده برنخورد ---
        self.user_code_var = tk.StringVar(value=initial_user_code)
        self.name_var = tk.StringVar()
        self.unit_var = tk.StringVar(value="عدد")
        self.min_var = tk.StringVar(value="0")
        self.cat_var = tk.StringVar(value="مصرفی")
        self.shelf_var = tk.StringVar()

        self._configure_window(master)
        self._build_form()
        if product is not None:
            self._load_product(product)
        self._bind_shortcuts()

    # ------------------------------------------------------------------ setup

    def _configure_window(self, master: tk.Misc) -> None:
        self.title("ویرایش کالا" if self.product else "کالای جدید")
        self.resizable(True, True)
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.configure(bg=T.BG)
        self.transient(master)
        self._center_on(master)
        self.grab_set()

    def _center_on(self, master: tk.Misc) -> None:
        self.update_idletasks()
        try:
            mx, my = master.winfo_rootx(), master.winfo_rooty()
            mw, mh = master.winfo_width(), master.winfo_height()
        except tk.TclError:
            mx = my = mw = mh = 0

        screen_w = max(self.winfo_screenwidth(), self.MIN_WIDTH)
        screen_h = max(self.winfo_screenheight(), self.MIN_HEIGHT)
        width = min(self.WIDTH, screen_w - 24)
        height = min(self.HEIGHT, screen_h - 80)
        width = max(min(width, screen_w), min(self.MIN_WIDTH, screen_w))
        height = max(min(height, screen_h), min(self.MIN_HEIGHT, screen_h))

        if mw <= 1 or mh <= 1:  # والد هنوز نگاشت نشده — مرکز صفحه
            x = (screen_w - width) // 2
            y = (screen_h - height) // 2
        else:
            x = mx + (mw - width) // 2
            y = my + (mh - height) // 2
            x = min(max(x, 0), max(screen_w - width, 0))
            y = min(max(y, 0), max(screen_h - height, 0))
        self.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")

    def _bind_shortcuts(self) -> None:
        self.bind("<Escape>", lambda _e: self.destroy())

    # ----------------------------------------------------------------- layout

    def _build_form(self) -> None:
        # نوار عملیات مستقل از محتوای فرم است تا با تغییر اندازه پنجره
        # یا مقیاس‌بندی ویندوز، دکمه‌ها پایین پنجره قابل مشاهده بمانند.
        buttons = ttk.Frame(self, padding=(16, 10))
        buttons.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Separator(self, orient="horizontal").pack(side=tk.BOTTOM, fill=tk.X)

        frame = ttk.Frame(self, padding=16)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        self._add_entry(frame, 0, "کد کالا:", self.user_code_var)
        self._add_entry(frame, 1, "نام کالا:", self.name_var)

        self._add_label(frame, 2, "واحد:")
        ttk.Combobox(
            frame, textvariable=self.unit_var, values=list(UNITS), width=30
        ).grid(row=2, column=1, sticky="ew", pady=5)

        self._add_entry(frame, 3, "حداقل موجودی:", self.min_var)

        self._add_label(frame, 4, "دسته:")
        ttk.Combobox(
            frame,
            textvariable=self.cat_var,
            values=list(CATEGORIES),
            state="readonly",
            width=30,
        ).grid(row=4, column=1, sticky="ew", pady=5)

        self._add_entry(frame, 5, "قفسه:", self.shelf_var)

        ttk.Button(
            buttons, text="ذخیره", style="Primary.TButton", command=self._save, width=12
        ).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(
            buttons, text="انصراف", style="Secondary.TButton", command=self.destroy, width=10
        ).pack(side=tk.RIGHT, padx=6)

    def _add_label(self, parent: ttk.Frame, row: int, text: str) -> ttk.Label:
        label = ttk.Label(parent, text=text)
        label.grid(row=row, column=0, sticky="e", pady=5, padx=4)
        return label

    def _add_entry(
        self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar
    ) -> ttk.Entry:
        self._add_label(parent, row, label)
        entry = ttk.Entry(parent, textvariable=var, width=30)
        entry.grid(row=row, column=1, sticky="ew", pady=5)
        entry.bind("<Return>", lambda _e: self._save())
        if row == 0:
            self.after_idle(entry.focus_set)
        return entry

    def _load_product(self, product: Product) -> None:
        self.user_code_var.set(product.user_code or product.code)
        self.name_var.set(product.name)
        self.unit_var.set(product.unit)
        self.min_var.set(self._fmt(product.min_stock))
        self.cat_var.set(product.category)
        self.shelf_var.set(product.shelf)

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _fmt(value: float) -> str:
        """نمایش فشرده عدد؛ بدون '.0' اضافی."""
        try:
            if float(value).is_integer():
                return str(int(value))
        except (TypeError, ValueError):
            pass
        return str(value)

    @staticmethod
    def _coerce_min_stock(raw: str) -> float:
        """تبدیل ورودی کاربر به عدد غیرمنفی؛ در صورت خطا ValueError با پیام فارسی."""
        text = (raw or "").strip() or "0"
        if text == "0":
            return 0.0

        # import تنبل تا از چرخهٔ وابستگی بین سرویس‌ها جلوگیری شود
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

    # ------------------------------------------------------------------- save

    def _save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            self._show_error("نام کالا را وارد کنید.")
            return

        user_code = self.user_code_var.get().strip()
        if not user_code:
            self._show_error("کد کالا را وارد کنید.")
            return

        try:
            min_stock = self._coerce_min_stock(self.min_var.get())
        except ValueError as exc:
            self._show_error(str(exc))
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

        try:
            if self.product is not None:
                self.service.update(
                    self.product.code, name, unit, min_stock, category, shelf, user_code
                )
                message = "کالا ویرایش شد."
            else:
                created = self.service.add(
                    name, unit, min_stock, category, shelf, user_code
                )
                message = f"کالا با کد «{created.user_code}» ثبت شد."
        except Exception as exc:  # noqa: BLE001 — نمایش خطای دامنه به کاربر
            logger.exception("Saving product failed")
            self._show_error(str(exc))
            return

        messagebox.showinfo("موفق", message, parent=self)
        try:
            if self.on_save is not None:
                self.on_save()
        except Exception:
            # خطای refresh والد نباید دیالوگ را باز نگه دارد
            logger.exception("on_save callback failed")
        finally:
            self.destroy()

    def _show_error(self, message: str) -> None:
        messagebox.showerror("خطا", message, parent=self)
