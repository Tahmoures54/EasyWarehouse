# -*- coding: utf-8 -*-
"""فرم افزودن/ویرایش کالا."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from app.config import CATEGORIES, UNITS
from app.models.product import Product
from app.services.product_service import ProductService
from app.ui import theme as T


class ProductForm(tk.Toplevel):
    """دیالوگ کالای جدید یا ویرایش."""

    def __init__(
        self,
        master: tk.Misc,
        service: ProductService,
        product: Optional[Product] = None,
        on_save: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(master)
        self.service = service
        self.product = product
        self.on_save = on_save
        self.title("ویرایش کالا" if product else "کالای جدید")
        self.geometry("440x350")
        self.resizable(False, False)
        self.configure(bg=T.BG)
        self.transient(master)
        self.grab_set()
        self._build()
        if product:
            self.user_code_var.set(product.user_code or product.code)
            self.name_var.set(product.name)
            self.unit_var.set(product.unit)
            self.min_var.set(self._fmt(product.min_stock))
            self.cat_var.set(product.category)
            self.shelf_var.set(product.shelf)

    @staticmethod
    def _fmt(v: float) -> str:
        return str(int(v)) if v == int(v) else str(v)

    def _build(self) -> None:
        f = ttk.Frame(self, padding=16)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="کد کالا:").grid(row=0, column=0, sticky="e", pady=5, padx=4)
        self.user_code_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.user_code_var, width=30).grid(row=0, column=1, sticky="w", pady=5)

        ttk.Label(f, text="نام کالا:").grid(row=1, column=0, sticky="e", pady=5, padx=4)
        self.name_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.name_var, width=30).grid(row=1, column=1, sticky="w", pady=5)

        ttk.Label(f, text="واحد:").grid(row=2, column=0, sticky="e", pady=5, padx=4)
        self.unit_var = tk.StringVar(value="عدد")
        ttk.Combobox(f, textvariable=self.unit_var, values=list(UNITS), width=28).grid(
            row=1, column=1, sticky="w", pady=5
        )

        ttk.Label(f, text="حداقل موجودی:").grid(row=3, column=0, sticky="e", pady=5, padx=4)
        self.min_var = tk.StringVar(value="0")
        ttk.Entry(f, textvariable=self.min_var, width=30).grid(row=3, column=1, sticky="w", pady=5)

        ttk.Label(f, text="دسته:").grid(row=4, column=0, sticky="e", pady=5, padx=4)
        self.cat_var = tk.StringVar(value="مصرفی")
        ttk.Combobox(f, textvariable=self.cat_var, values=list(CATEGORIES), state="readonly", width=28).grid(
            row=4, column=1, sticky="w", pady=5
        )

        ttk.Label(f, text="قفسه:").grid(row=5, column=0, sticky="e", pady=5, padx=4)
        self.shelf_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.shelf_var, width=30).grid(row=5, column=1, sticky="w", pady=5)

        bf = ttk.Frame(f)
        bf.grid(row=6, column=0, columnspan=2, pady=16)
        ttk.Button(bf, text="ذخیره", style="Primary.TButton", command=self._save, width=12).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(bf, text="انصراف", style="Secondary.TButton", command=self.destroy, width=10).pack(
            side=tk.LEFT, padx=6
        )

    def _save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("خطا", "نام کالا را وارد کنید.", parent=self)
            return
        try:
            from app.services.transaction_service import parse_positive_qty

            raw = self.min_var.get().strip() or "0"
            if raw == "0":
                mn = 0.0
            else:
                mn = parse_positive_qty(raw)
        except ValueError:
            try:
                mn = float(self.min_var.get().replace(",", ".") or "0")
                if mn < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("خطا", "حداقل موجودی باید عدد غیرمنفی باشد.", parent=self)
                return
        unit = self.unit_var.get().strip() or "عدد"
        cat = self.cat_var.get()
        shelf = self.shelf_var.get().strip()
        user_code = self.user_code_var.get().strip()
        if not user_code:
            messagebox.showerror("خطا", "کد کالا را وارد کنید.", parent=self)
            return
        warnings = self.service.duplicate_warnings(name, user_code, self.product.code if self.product else None)
        if warnings and not messagebox.askyesno("هشدار تکراری بودن کالا", "\n".join(warnings) + "\n\nبا وجود هشدار، ثبت را ادامه می‌دهید؟", parent=self):
            return
        try:
            if self.product:
                self.service.update(self.product.code, name, unit, mn, cat, shelf, user_code)
                messagebox.showinfo("موفق", "کالا ویرایش شد.", parent=self)
            else:
                p = self.service.add(name, unit, mn, cat, shelf, user_code)
                messagebox.showinfo("موفق", f"کالا با کد «{p.user_code}» ثبت شد.", parent=self)
        except Exception as exc:
            messagebox.showerror("خطا", str(exc), parent=self)
            return
        if self.on_save:
            self.on_save()
        self.destroy()
