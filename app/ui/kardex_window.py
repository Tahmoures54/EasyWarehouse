# -*- coding: utf-8 -*-
"""پنجره گزارش کاردکس یک کالا."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from app.services.product_service import ProductService
from app.services.report_service import ReportService
from app.ui import theme as T
from app.utils.date_utils import from_jalali, to_jalali
from app.services.print_service import build_kardex_html

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
        self._visible_rows = []
        self._all_rows = []
        self._product = None
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
        ttk.Label(top, text="از تاریخ شمسی").grid(row=0, column=2, padx=4)
        self.start_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.start_var, width=12).grid(row=0, column=3, padx=4)
        ttk.Label(top, text="تا تاریخ شمسی").grid(row=0, column=4, padx=4)
        self.end_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.end_var, width=12).grid(row=0, column=5, padx=4)
        ttk.Label(top, text="نوع گردش").grid(row=1, column=0, padx=4, pady=4)
        self.type_var = tk.StringVar(value="همه گردش‌ها")
        self.type_combo = ttk.Combobox(top, textvariable=self.type_var, values=("همه گردش‌ها", "ورود", "خروج", "عودت"), state="readonly", width=14)
        self.type_combo.grid(row=1, column=1, padx=4, pady=4, sticky="w")
        self.type_combo.bind("<<ComboboxSelected>>", lambda _event: self.load())
        ttk.Label(top, text="نمونه: ۱۴۰۵/۰۷/۲۹").grid(row=1, column=2, columnspan=2, padx=4, sticky="w")
        ttk.Button(top, text="نمایش کاردکس", command=self.load).grid(row=1, column=4, padx=4)
        ttk.Button(top, text="چاپ / ذخیره PDF", command=self.print_report).grid(row=1, column=5, columnspan=2, padx=4)
        top.columnconfigure(1, weight=1)

        self.summary_var = tk.StringVar(value="کالا را انتخاب کنید. برای کل سابقه، تاریخ‌ها را خالی بگذارید.")
        ttk.Label(self, textvariable=self.summary_var, padding=(14, 0, 14, 8), justify=tk.LEFT).pack(anchor="w")

        body = ttk.Frame(self, padding=(12, 0, 12, 8))
        body.pack(fill=tk.BOTH, expand=True)
        cols = ("id", "document_no", "date", "type", "incoming", "outgoing", "balance", "unit", "note")
        self.tree = ttk.Treeview(body, columns=cols, show="headings")
        heads = ("شماره گردش", "شماره سند", "تاریخ", "شرح", "ورود", "خروج", "مانده", "واحد", "توضیحات")
        widths = (75, 95, 95, 120, 70, 70, 80, 60, 230)
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
            start = self._normalize_date(self.start_var.get())
            end = self._normalize_date(self.end_var.get())
            rows = self.reports.kardex_rows(code, start, end)
            self._all_rows = rows
            self._product = self.ps.get(code)
            selected_type = self.type_var.get()
            display_rows = [row for row in rows if row["type"] == "مانده ابتدای دوره" or selected_type == "همه گردش‌ها" or row["type"] == selected_type]
            self._visible_rows = display_rows
            self.tree.delete(*self.tree.get_children())
            for row in display_rows:
                try:
                    date_label = to_jalali(row["date"])
                except (ValueError, TypeError):
                    date_label = row["date"]
                self.tree.insert("", tk.END, values=(
                    row["id"], row.get("document_no", ""), date_label, row["type"],
                    f'{row["incoming"]:g}', f'{row["outgoing"]:g}',
                    f'{row["balance"]:g}', row["unit"], row["note"]
                ))
            product = self.ps.get(code)
            opening_row = next((row for row in rows if row["type"] == "مانده ابتدای دوره"), None)
            opening_balance = opening_row["balance"] if opening_row else 0.0
            movements = [row for row in rows if row["type"] != "مانده ابتدای دوره"]
            total_in = sum(row["incoming"] for row in movements)
            total_out = sum(row["outgoing"] for row in movements)
            final_balance = rows[-1]["balance"] if rows else opening_balance
            product_name = product.name if product else code
            product_code = (product.user_code or product.code) if product else code
            unit = product.unit if product else ""
            self.summary_var.set(
                f"کالا: {product_name}  |  کد: {product_code}  |  واحد: {unit}\n"
                f"مانده ابتدای دوره: {opening_balance:g}  |  جمع ورود: {total_in:g}  |  "
                f"جمع خروج: {total_out:g}  |  مانده پایان گزارش: {final_balance:g} {unit}\n"
                f"تعداد گردش‌ها: {len(movements)}"
            )
        except Exception as exc:
            logger.exception("Kardex report failed")
            messagebox.showerror("خطا در کاردکس", str(exc), parent=self)

    @staticmethod
    def _normalize_date(value):
        value = (value or "").strip()
        if not value:
            return None
        try:
            return from_jalali(value)
        except ValueError:
            from datetime import date
            try:
                return date.fromisoformat(value).isoformat()
            except ValueError as exc:
                raise ValueError("تاریخ را شمسی مانند ۱۴۰۵/۰۷/۲۹ وارد کنید.") from exc

    def print_report(self):
        if not self._selected_code() or not self._all_rows:
            messagebox.showwarning("چاپ کاردکس", "ابتدا یک کاردکس دارای گردش نمایش دهید.", parent=self)
            return
        product = self._product
        html_doc = build_kardex_html(product, self._visible_rows, self.start_var.get().strip(), self.end_var.get().strip(), self.type_var.get())
        path = filedialog.asksaveasfilename(parent=self, title="ذخیره گزارش چاپی کاردکس", defaultextension=".html", initialfile=f"kardex-{product.code}.html", filetypes=[("گزارش HTML قابل چاپ", "*.html")])
        if not path:
            return
        from pathlib import Path
        target = Path(path)
        target.write_text(html_doc, encoding="utf-8")
        opened = webbrowser.open(target.resolve().as_uri())
        if opened:
            messagebox.showinfo("چاپ کاردکس", "گزارش در مرورگر باز شد؛ از گزینه چاپ مرورگر برای چاپ یا ذخیره PDF استفاده کنید.", parent=self)
        else:
            messagebox.showwarning("چاپ کاردکس", f"گزارش ذخیره شد اما مرورگر باز نشد:\n{target}", parent=self)

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
                path, code, self._normalize_date(self.start_var.get()),
                self._normalize_date(self.end_var.get())
            )
            messagebox.showinfo("کاردکس", f"گزارش ذخیره شد:\n{saved}", parent=self)
        except Exception as exc:
            logger.exception("Kardex export failed")
            messagebox.showerror("خطا در خروجی", str(exc), parent=self)
