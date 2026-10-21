# -*- coding: utf-8 -*-
"""پنجره گزارش کاردکس یک کالا."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app.services.product_service import ProductService
from app.services.report_service import ReportService
from app.ui import theme as T
from app.utils.date_utils import to_jalali

logger = logging.getLogger(__name__)


class KardexWindow(tk.Toplevel):
    def __init__(self, master, product_service: ProductService, reports: ReportService):
        super().__init__(master)
        self.title("کاردکس کالا")
        self.geometry("1050x600")
        self.minsize(850, 480)
        self.transient(master)
        self.ps = product_service
        self.reports = reports
        self._products = self.ps.all()
        self._by_label = {}
        for p in self._products:
            label = f"{p.user_code or p.code} - {p.name} ⟦{p.code}⟧"
            self._by_label[label] = p.code

        top = ttk.Frame(self, padding=12)
        top.pack(fill=tk.X)
        ttk.Label(top, text="کالا").grid(row=0, column=0, padx=4, pady=4)
        self.product_var = tk.StringVar()
        self.product_combo = ttk.Combobox(
            top, textvariable=self.product_var, values=list(self._by_label),
            state="readonly", width=42
        )
        self.product_combo.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ttk.Label(top, text="از تاریخ (میلادی YYYY-MM-DD)").grid(row=0, column=2, padx=4)
        self.start_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.start_var, width=14).grid(row=0, column=3, padx=4)
        ttk.Label(top, text="تا تاریخ").grid(row=0, column=4, padx=4)
        self.end_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.end_var, width=14).grid(row=0, column=5, padx=4)
        ttk.Button(top, text="نمایش کاردکس", command=self.load).grid(row=0, column=6, padx=4)
        top.columnconfigure(1, weight=1)

        self.summary_var = tk.StringVar(value="کالا را انتخاب کنید. برای کل سابقه، تاریخ‌ها را خالی بگذارید.")
        ttk.Label(self, textvariable=self.summary_var, padding=(14, 0, 14, 8)).pack(anchor="w")

        body = ttk.Frame(self, padding=(12, 0, 12, 8))
        body.pack(fill=tk.BOTH, expand=True)
        cols = ("id", "date", "type", "incoming", "outgoing", "balance", "unit", "note")
        self.tree = ttk.Treeview(body, columns=cols, show="headings")
        heads = ("شماره گردش", "تاریخ", "شرح", "ورود", "خروج", "مانده", "واحد", "توضیحات")
        widths = (85, 100, 130, 75, 75, 85, 70, 260)
        for col, head, width in zip(cols, heads, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=width, minwidth=55, anchor="center")
        yscroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree.yview)
        xscroll = ttk.Scrollbar(body, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        bottom = ttk.Frame(self, padding=12)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="خروجی Excel (CSV)", command=self.export).pack(side=tk.LEFT)
        ttk.Button(bottom, text="بستن", command=self.destroy).pack(side=tk.RIGHT)
        if self._by_label:
            self.product_combo.current(0)
            self.load()

    def _selected_code(self):
        return self._by_label.get(self.product_var.get())

    def load(self):
        code = self._selected_code()
        if not code:
            messagebox.showwarning("کاردکس", "ابتدا یک کالا انتخاب کنید.", parent=self)
            return
        try:
            rows = self.reports.kardex_rows(
                code, self.start_var.get().strip() or None, self.end_var.get().strip() or None
            )
            self.tree.delete(*self.tree.get_children())
            for row in rows:
                try:
                    date_label = to_jalali(row["date"])
                except (ValueError, TypeError):
                    date_label = row["date"]
                self.tree.insert("", tk.END, values=(
                    row["id"], date_label, row["type"],
                    f'{row["incoming"]:g}', f'{row["outgoing"]:g}',
                    f'{row["balance"]:g}', row["unit"], row["note"]
                ))
            product = self.ps.get(code)
            final_balance = rows[-1]["balance"] if rows else 0.0
            self.summary_var.set(
                f"کالا: {product.name if product else code} | "
                f"تعداد ردیف‌ها: {len(rows)} | مانده پایان گزارش: {final_balance:g} "
                f"{product.unit if product else ''}"
            )
        except Exception as exc:
            logger.exception("Kardex report failed")
            messagebox.showerror("خطا در کاردکس", str(exc), parent=self)

    def export(self):
        code = self._selected_code()
        if not code:
            messagebox.showwarning("کاردکس", "ابتدا یک کالا انتخاب کنید.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="ذخیره کاردکس کالا", defaultextension=".csv",
            initialfile="kardex.csv", filetypes=[("CSV سازگار با Excel", "*.csv")]
        )
        if not path:
            return
        try:
            saved = self.reports.export_kardex_csv(
                path, code, self.start_var.get().strip() or None,
                self.end_var.get().strip() or None
            )
            messagebox.showinfo("کاردکس", f"گزارش ذخیره شد:\n{saved}", parent=self)
        except Exception as exc:
            logger.exception("Kardex export failed")
            messagebox.showerror("خطا در خروجی", str(exc), parent=self)
