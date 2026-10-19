# -*- coding: utf-8 -*-
"""پنجره اصلی برنامه."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional

from app.config import APP_TITLE, APP_VERSION, APP_GEOMETRY, APP_MIN_SIZE, ICON_PATH, get_db_path
from app.database.db_manager import DB, DatabaseError
from app.services.product_service import ProductService
from app.services.transaction_service import TransactionService
from app.services.backup_service import BackupService
from app.services.report_service import ReportService
from app.ui.theme import apply_theme
from app.ui import theme as T
from app.ui.forms.transaction_form import TransactionForm
from app.ui.forms.product_form import ProductForm
from app.ui.widgets.table_view import TxTable
from app.ui.help_window import HelpWindow
from app.ui.about_window import AboutWindow


class MainWindow(tk.Tk):
    """رابط اصلی مدیریت انبار."""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_GEOMETRY)
        self.minsize(*APP_MIN_SIZE)
        apply_theme(self)
        self._set_icon()

        try:
            self.db = DB()
        except DatabaseError as exc:
            messagebox.showerror("خطای دیتابیس", str(exc))
            self.destroy()
            return

        self.ps = ProductService(self.db)
        self.ts = TransactionService(self.db)
        self.backup = BackupService()
        self.reports = ReportService(self.db)

        self._build_menu()
        self._build_ui()
        self.bind("<F1>", lambda e: self._help())
        self.refresh()

    def _set_icon(self) -> None:
        try:
            path = ICON_PATH
            if path.exists():
                self.iconbitmap(str(path))
        except Exception:
            pass

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        file_m = tk.Menu(menubar, tearoff=0)
        file_m.add_command(label="پشتیبان‌گیری...", command=self._do_backup)
        file_m.add_command(label="بازیابی...", command=self._do_restore)
        file_m.add_separator()
        file_m.add_command(label="خروج", command=self.destroy)
        menubar.add_cascade(label="پرونده", menu=file_m)

        prod_m = tk.Menu(menubar, tearoff=0)
        prod_m.add_command(label="کالای جدید", command=self._add_product)
        prod_m.add_command(label="لیست کالاها", command=self._list_products)
        menubar.add_cascade(label="کالاها", menu=prod_m)

        report_m = tk.Menu(menubar, tearoff=0)
        report_m.add_command(label="گزارش وضعیت موجودی (CSV)...", command=self._export_inventory_report)
        report_m.add_command(label="گزارش کمبود و ناموجودی (CSV)...", command=self._export_low_stock_report)
        report_m.add_command(label="گزارش گردش تراکنش‌ها (CSV)...", command=self._export_transaction_report)
        menubar.add_cascade(label="گزارش‌ها", menu=report_m)

        help_m = tk.Menu(menubar, tearoff=0)
        help_m.add_command(label="راهنمای کاربر\tF1", command=self._help)
        help_m.add_command(label="درباره برنامه", command=self._about)
        menubar.add_cascade(label="راهنما", menu=help_m)
        self.config(menu=menubar)

    def _build_ui(self) -> None:
        # هدر
        header = ttk.Frame(self, style="Header.TFrame", height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        ttk.Label(header, text="  EasyWarehouse", style="Header.TLabel").pack(side=tk.LEFT, padx=8, pady=12)
        ttk.Label(header, text=f"v{APP_VERSION}  ", style="Version.TLabel").pack(side=tk.RIGHT, padx=12)

        # فیلتر
        bar = ttk.Frame(self, padding=(10, 6))
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="فیلتر دسته:").pack(side=tk.LEFT)
        self.cat_filter = tk.StringVar(value="همه")
        cb = ttk.Combobox(
            bar,
            textvariable=self.cat_filter,
            values=["همه", "مصرفی", "تکنیکال", "عمومی"],
            state="readonly",
            width=12,
        )
        cb.pack(side=tk.LEFT, padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.count_lbl = ttk.Label(bar, text="", style="Muted.TLabel")
        self.count_lbl.pack(side=tk.RIGHT)

        # فرم
        self.form = TransactionForm(self, self.ps, self.ts, on_ok=self.refresh)
        self.form.pack(fill=tk.X, padx=10, pady=6)

        # میانی
        mid = ttk.Frame(self)
        mid.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        left = ttk.LabelFrame(mid, text=" تراکنش‌ها ", style="Card.TLabelframe", padding=8)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.table = TxTable(left)
        self.table.pack(fill=tk.BOTH, expand=True)
        tb = ttk.Frame(left)
        tb.pack(fill=tk.X, pady=4)
        ttk.Button(tb, text="حذف انتخاب‌شده", style="Danger.TButton", command=self._del_tx).pack(side=tk.LEFT)
        ttk.Button(tb, text="به‌روزرسانی", style="Secondary.TButton", command=self.refresh).pack(side=tk.LEFT, padx=6)

        right = ttk.LabelFrame(mid, text=" کم‌موجودی ", style="Card.TLabelframe", padding=8)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        self.low_list = tk.Listbox(
            right, width=34, height=14, font=T.FONT, bg=T.CARD_BG, fg=T.TEXT,
            selectbackground=T.PRIMARY, relief=tk.FLAT, highlightthickness=0,
        )
        self.low_list.pack(fill=tk.BOTH, expand=True)

        # وضعیت
        status = ttk.Frame(self, style="Status.TFrame")
        status.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="آماده")
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel").pack(
            side=tk.LEFT, padx=10, pady=4
        )
        ttk.Label(status, text=f"DB: {get_db_path()}", style="Status.TLabel").pack(
            side=tk.RIGHT, padx=10, pady=4
        )

    def _filter_cat(self) -> Optional[str]:
        v = self.cat_filter.get()
        return None if v == "همه" else v

    def refresh(self) -> None:
        try:
            txs = self.ts.all()
            self.table.load(txs)
            cat = self._filter_cat()
            self.form.refresh(cat)
            products = self.ps.all(cat)
            self.count_lbl.config(text=f"نمایش: {len(products)}  |  کل کالا: {self.ps.count()}")
            self.low_list.delete(0, tk.END)
            lows = sorted([p for p in products if p.is_low() or p.is_critical()], key=lambda p: p.stock)
            if not lows:
                self.low_list.insert(tk.END, "✓ موجودی‌ها مناسب هستند")
            for p in lows[:60]:
                mark = "🔴" if p.is_critical() else "🟠"
                self.low_list.insert(tk.END, f"{mark} {p.name}: {p.stock:g} {p.unit}")
            self.status_var.set(f"تراکنش‌ها: {len(txs)}")
        except Exception as exc:
            messagebox.showerror("خطا", str(exc))

    def _add_product(self) -> None:
        ProductForm(self, self.ps, on_save=self.refresh)

    def _list_products(self) -> None:
        win = tk.Toplevel(self)
        win.title("کتابخانه کالاها")
        win.geometry("760x420")
        win.configure(bg=T.BG)
        cols = ("code", "name", "unit", "cat", "shelf", "min", "stock")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=14)
        for c, h, w in [
            ("code", "کد", 55), ("name", "نام", 190), ("unit", "واحد", 55),
            ("cat", "دسته", 70), ("shelf", "قفسه", 90), ("min", "حداقل", 55), ("stock", "موجودی", 65),
        ]:
            tree.heading(c, text=h)
            tree.column(c, width=w, anchor="center")
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def load() -> None:
            tree.delete(*tree.get_children())
            for p in self.ps.all():
                tree.insert("", tk.END, values=(
                    p.code, p.name, p.unit, p.category, p.shelf or "—",
                    f"{p.min_stock:g}", f"{p.stock:g}",
                ))

        def edit() -> None:
            sel = tree.selection()
            if not sel:
                return
            code = tree.item(sel[0], "values")[0]
            p = self.ps.get(code)
            if p:
                ProductForm(win, self.ps, product=p, on_save=lambda: (load(), self.refresh()))

        def delete() -> None:
            sel = tree.selection()
            if not sel:
                return
            code = tree.item(sel[0], "values")[0]
            if not messagebox.askyesno("تأیید", f"حذف کالای {code}؟", parent=win):
                return
            try:
                self.ps.delete(code)
                load()
                self.refresh()
            except Exception as exc:
                messagebox.showerror("خطا", str(exc), parent=win)

        bf = ttk.Frame(win)
        bf.pack(fill=tk.X, padx=10, pady=6)
        ttk.Button(bf, text="جدید", style="Primary.TButton",
                   command=lambda: ProductForm(win, self.ps, on_save=lambda: (load(), self.refresh()))).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="ویرایش", style="Secondary.TButton", command=edit).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="حذف", style="Danger.TButton", command=delete).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="بستن", command=win.destroy).pack(side=tk.RIGHT)
        load()

    def _del_tx(self) -> None:
        tid = self.table.selected_id()
        if tid is None:
            messagebox.showwarning("توجه", "یک ردیف را از جدول انتخاب کنید.")
            return
        if not messagebox.askyesno("تأیید", f"حذف تراکنش شماره {tid}؟"):
            return
        try:
            self.ts.delete(tid)
            self.refresh()
        except Exception as exc:
            messagebox.showerror("خطا", str(exc))

    def _do_backup(self) -> None:
        dest = filedialog.askdirectory(title="انتخاب پوشه پشتیبان")
        if not dest:
            return
        try:
            path = self.backup.backup(dest)
            messagebox.showinfo("پشتیبان‌گیری", f"فایل ذخیره شد:\n{path}")
        except Exception as exc:
            messagebox.showerror("خطا", str(exc))

    def _do_restore(self) -> None:
        path = filedialog.askopenfilename(
            title="انتخاب فایل پشتیبان",
            filetypes=[("Database", "*.db *.sqlite *.sqlite3"), ("All", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno("هشدار", "دیتابیس فعلی جایگزین می‌شود. ادامه می‌دهید؟"):
            return
        try:
            self.backup.restore(path)
            self.db = DB()
            self.ps = ProductService(self.db)
            self.ts = TransactionService(self.db)
            self.refresh()
            messagebox.showinfo("بازیابی", "بازیابی با موفقیت انجام شد.")
        except Exception as exc:
            messagebox.showerror("خطا", str(exc))

    def _export_inventory_report(self) -> None:
        self._save_report("گزارش موجودی", "inventory.csv", lambda path: self.reports.export_inventory_csv(path))

    def _export_low_stock_report(self) -> None:
        self._save_report("گزارش کمبود موجودی", "low-stock.csv", lambda path: self.reports.export_inventory_csv(path, low_only=True))

    def _export_transaction_report(self) -> None:
        self._save_report("گزارش گردش تراکنش‌ها", "transactions.csv", lambda path: self.reports.export_transactions_csv(path))

    def _save_report(self, title: str, filename: str, exporter) -> None:
        path = filedialog.asksaveasfilename(title=title, defaultextension=".csv", initialfile=filename, filetypes=[("CSV سازگار با Excel", "*.csv")])
        if not path:
            return
        try:
            saved = exporter(path)
            messagebox.showinfo(title, f"گزارش ذخیره شد:\n{saved}")
        except Exception as exc:
            messagebox.showerror("خطا در تهیه گزارش", str(exc))

    def _help(self) -> None:
        HelpWindow(self)

    def _about(self) -> None:
        AboutWindow(self)
