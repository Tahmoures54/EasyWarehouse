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
        self.geometry("1280x850")
        self.minsize(1000, 680)
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
        self.bind("<Control-f>", self._focus_transaction_search)
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
        """داشبورد اصلی با اولویت عملیات پرتکرار و خوانایی سریع."""
        self.configure(bg=T.BG)

        # هدر اصلی
        header = ttk.Frame(self, style="Header.TFrame", padding=(22, 14))
        header.pack(fill=tk.X)
        header.grid_columnconfigure(0, weight=1)
        title_box = ttk.Frame(header, style="Header.TFrame")
        title_box.grid(row=0, column=0, sticky="w")
        ttk.Label(title_box, text="EasyWarehouse", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            title_box,
            text="مرکز کنترل موجودی و گردش کالا",
            style="Header.Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        head_right = ttk.Frame(header, style="Header.TFrame")
        head_right.grid(row=0, column=1, sticky="e")
        ttk.Label(head_right, text=f"نسخه {APP_VERSION}", style="Version.TLabel").pack(anchor="e")
        ttk.Label(head_right, text="داشبورد انبار", style="Header.Subtitle.TLabel").pack(anchor="e", pady=(4, 0))

        # شاخص‌های کلیدی
        metrics = ttk.Frame(self, padding=(16, 12, 16, 4))
        metrics.pack(fill=tk.X)
        for col in range(4):
            metrics.columnconfigure(col, weight=1, uniform="metric")
        self.metric_products = self._metric_card(metrics, 0, "تعداد کالاها", "۰", "کالا در فهرست", "#087F8C")
        self.metric_transactions = self._metric_card(metrics, 1, "گردش‌های ثبت‌شده", "۰", "ورود، خروج و عودت", "#2563EB")
        self.metric_low = self._metric_card(metrics, 2, "نیازمند بررسی", "۰", "کمتر از حداقل موجودی", "#D97706")
        self.metric_zero = self._metric_card(metrics, 3, "ناموجود", "۰", "کالا با موجودی صفر یا کمتر", "#DC2626")

        # میانبرهای عملیاتی
        quick = ttk.Frame(self, padding=(16, 5, 16, 10))
        quick.pack(fill=tk.X)
        ttk.Label(quick, text="عملیات سریع", style="Section.TLabel").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(
            quick, text="▦  فهرست و کدگذاری کالا", style="Primary.TButton",
            command=self._list_products,
        ).pack(side=tk.LEFT, padx=(0, 7), ipady=3)
        ttk.Button(
            quick, text="+  ثبت کالای جدید", style="Secondary.TButton",
            command=self._add_product,
        ).pack(side=tk.LEFT, padx=(0, 7), ipady=3)
        ttk.Button(
            quick, text="⇩  خروجی گزارش موجودی", style="Secondary.TButton",
            command=self._export_inventory_report,
        ).pack(side=tk.LEFT, padx=(0, 7), ipady=3)
        ttk.Label(quick, text="جست‌وجوی گردش‌ها: Ctrl+F", style="Muted.TLabel").pack(side=tk.RIGHT)

        # فرم ثبت عملیات
        form_wrap = ttk.Frame(self, padding=(16, 2, 16, 8))
        form_wrap.pack(fill=tk.X)
        ttk.Label(form_wrap, text="ثبت گردش کالا", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        self.form = TransactionForm(form_wrap, self.ps, self.ts, on_ok=self.refresh)
        self.form.pack(fill=tk.X)

        # ناحیه کاری
        mid = ttk.Frame(self, padding=(16, 2, 16, 12))
        mid.pack(fill=tk.BOTH, expand=True)
        mid.columnconfigure(0, weight=4)
        mid.columnconfigure(1, weight=1, minsize=230)
        mid.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(mid, text="  گردش کالاها  ", style="Card.TLabelframe", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        toolbar = ttk.Frame(left)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(toolbar, text="جست‌وجو", style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 7))
        self.tx_search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.tx_search_var)
        self.transaction_search_entry = search_entry
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        search_entry.bind("<KeyRelease>", lambda _event: self.table.filter(self.tx_search_var.get()))
        search_entry.bind("<Escape>", self._clear_transaction_search)
        ttk.Button(toolbar, text="پاک‌کردن", style="Ghost.TButton", command=self._clear_transaction_search).pack(side=tk.LEFT, padx=(6, 0))
        self.table = TxTable(left)
        self.table.pack(fill=tk.BOTH, expand=True)
        table_actions = ttk.Frame(left)
        table_actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(table_actions, text="حذف گردش انتخاب‌شده", style="Danger.TButton", command=self._del_tx).pack(side=tk.LEFT)
        ttk.Button(table_actions, text="تازه‌سازی", style="Ghost.TButton", command=self.refresh).pack(side=tk.LEFT, padx=6)

        right = ttk.LabelFrame(mid, text="  هشدارهای موجودی  ", style="Card.TLabelframe", padding=10)
        right.grid(row=0, column=1, sticky="nsew")
        ttk.Label(
            right, text="مواردی که بهتر است بررسی شوند",
            style="Muted.TLabel", wraplength=210,
        ).pack(anchor="w", pady=(0, 8))
        self.low_list = tk.Listbox(
            right, width=28, height=12, font=T.FONT, bg=T.CARD_BG, fg=T.TEXT,
            selectbackground=T.PRIMARY, selectforeground="#FFFFFF", relief=tk.FLAT,
            highlightthickness=1, highlightbackground=T.CARD_BORDER, activestyle="none",
        )
        self.low_list.pack(fill=tk.BOTH, expand=True)
        ttk.Button(
            right, text="مشاهده فهرست کالاها", style="Secondary.TButton",
            command=self._list_products,
        ).pack(fill=tk.X, pady=(9, 0))

        # نوار وضعیت پایین
        status = ttk.Frame(self, style="Status.TFrame", padding=(12, 6))
        status.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="آماده")
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT)
        ttk.Label(status, text="ذخیره‌سازی محلی و خودکار", style="Status.TLabel").pack(side=tk.RIGHT, padx=(0, 12))
        ttk.Label(status, text=f"پایگاه داده: {get_db_path()}", style="Status.TLabel").pack(side=tk.RIGHT)

    def _metric_card(self, parent, column: int, title: str, value: str, hint: str, accent: str):
        card = ttk.Frame(parent, style="Metric.TFrame", padding=(14, 10))
        card.grid(row=0, column=column, sticky="nsew", padx=5, pady=2)
        tk.Frame(card, bg=accent, height=4).pack(fill=tk.X, pady=(0, 7))
        # رنگ نوار بالایی با استایل مستقل قابل تنظیم است؛ مقدار شاخص درشت و واضح می‌ماند.
        ttk.Label(card, text=title, style="MetricLabel.TLabel").pack(anchor="w")
        value_label = ttk.Label(card, text=value, style="MetricValue.TLabel")
        value_label.pack(anchor="w", pady=(3, 0))
        ttk.Label(card, text=hint, style="MetricHint.TLabel").pack(anchor="w", pady=(2, 0))
        return value_label

    def _focus_transaction_search(self, _event=None):
        self.transaction_search_entry.focus_set()
        self.transaction_search_entry.selection_range(0, tk.END)
        return "break"

    def _clear_transaction_search(self, _event=None):
        self.tx_search_var.set("")
        self.table.filter("")
        return "break"

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
            total_products = self.ps.count()
            all_products = self.ps.all()
            all_lows = [p for p in all_products if p.is_low() or p.is_critical()]
            zero_count = sum(1 for p in all_products if p.stock <= 0)
            self.metric_products.config(text=f"{total_products:,}")
            self.metric_transactions.config(text=f"{len(txs):,}")
            self.metric_low.config(text=f"{len(all_lows):,}")
            self.metric_zero.config(text=f"{zero_count:,}")
            self.low_list.delete(0, tk.END)
            if not all_lows:
                self.low_list.insert(tk.END, "✓  وضعیت موجودی مناسب است")
            for p in sorted(all_lows, key=lambda item: item.stock)[:60]:
                label = "●" if p.is_critical() else "○"
                self.low_list.insert(tk.END, f"{label}  {p.name}: {p.stock:g} {p.unit}")
            self.status_var.set(f"آماده  |  {len(txs):,} گردش ثبت‌شده")
        except Exception as exc:
            messagebox.showerror("خطا", str(exc))

    def _add_product(self) -> None:
        ProductForm(self, self.ps, on_save=self.refresh)

    def _list_products(self) -> None:
        win = tk.Toplevel(self)
        win.title("کتابخانه کالاها")
        win.geometry("1040x520")
        win.minsize(960, 460)
        win.configure(bg=T.BG)
        cols = ("code", "name", "unit", "cat", "shelf", "min", "stock")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=14)
        for c, h, w in [
            ("code", "کد", 55), ("name", "نام", 190), ("unit", "واحد", 55),
            ("cat", "دسته", 70), ("shelf", "قفسه", 90), ("min", "حداقل", 55), ("stock", "موجودی", 65),
        ]:
            tree.heading(c, text=h)
            tree.column(c, width=w, anchor="center")
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))
        searchbar = ttk.Frame(win)
        searchbar.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(searchbar, text="جست‌وجوی کالا (نام یا کد):").pack(side=tk.LEFT, padx=(0, 6))
        product_search_var = tk.StringVar()
        product_search = ttk.Entry(searchbar, textvariable=product_search_var)
        product_search.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def load() -> None:
            tree.delete(*tree.get_children())
            query = product_search_var.get().strip().casefold()
            for p in self.ps.all():
                if query and query not in f"{p.code} {p.name} {p.category} {p.shelf or ''}".casefold():
                    continue
                tree.insert("", tk.END, iid=p.code, values=(
                    p.user_code or p.code, p.name, p.unit, p.category, p.shelf or "—",
                    f"{p.min_stock:g}", f"{p.stock:g}",
                ))

        def edit() -> None:
            sel = tree.selection()
            if not sel:
                return
            code = sel[0]
            p = self.ps.get(code)
            if p:
                ProductForm(win, self.ps, product=p, on_save=lambda: (load(), self.refresh()))

        def delete() -> None:
            sel = tree.selection()
            if not sel:
                return
            code = sel[0]
            selected = tree.item(sel[0], "values")
            if not messagebox.askyesno("تأیید", f"حذف کالای {selected[0]} - {selected[1]}؟", parent=win):
                return
            try:
                self.ps.delete(code)
                load()
                self.refresh()
            except Exception as exc:
                messagebox.showerror("خطا", str(exc), parent=win)

        bf = ttk.Frame(win)
        bf.pack(fill=tk.X, padx=10, pady=6)
        product_search.bind("<KeyRelease>", lambda _event: load())
        ttk.Button(bf, text="جدید", style="Primary.TButton",
                   command=lambda: ProductForm(win, self.ps, on_save=lambda: (load(), self.refresh()))).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="ویرایش", style="Secondary.TButton", command=edit).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="حذف", style="Danger.TButton", command=delete).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="دریافت الگوی Excel", style="Secondary.TButton",
                   command=lambda: self._download_product_template(win)).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="ورود از Excel", style="Primary.TButton",
                   command=lambda: self._import_products_excel(win, load)).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="بستن", command=win.destroy).pack(side=tk.RIGHT)
        load()

    def _download_product_template(self, parent) -> None:
        path = filedialog.asksaveasfilename(
            parent=parent, title="ذخیره الگوی ورود کالا",
            defaultextension=".xlsx", initialfile="easywarehouse-products-template.xlsx",
            filetypes=[("فایل Excel", "*.xlsx")],
        )
        if not path:
            return
        try:
            from app.services.product_excel_service import create_product_template
            create_product_template(path)
            messagebox.showinfo(
                "الگوی Excel آماده است",
                "فایل الگو ذخیره شد. کد و نام کالا را وارد کنید؛ تکراری بودن هرکدام هشدار می‌دهد اما با تأیید شما مانع ورود نیست. شناسه داخلی خودکار ساخته می‌شود و موجودی اولیه صفر خواهد بود.",
                parent=parent,
            )
        except Exception as exc:
            messagebox.showerror("خطا در ساخت الگو", str(exc), parent=parent)

    def _import_products_excel(self, parent, reload_products) -> None:
        path = filedialog.askopenfilename(
            parent=parent, title="انتخاب فایل Excel کالاها",
            filetypes=[("فایل Excel", "*.xlsx")],
        )
        if not path:
            return
        try:
            from app.services.product_excel_service import preview_product_import, import_product_rows
            rows, errors, total_rows, warnings = preview_product_import(path, self.ps)
            if not rows and not errors:
                messagebox.showinfo("ورود کالا", "فایل ردیف کالای قابل ورود ندارد.", parent=parent)
                return
            preview = [
                f"ردیف‌های قابل ورود: {len(rows)}",
                f"ردیف‌های ردشده: {len(errors)}",
                f"تعداد ردیف‌های بررسی‌شده: {total_rows}",
            ]
            if errors:
                preview.extend(["", "موارد نیازمند اصلاح:"])
                preview.extend(errors[:12])
                if len(errors) > 12:
                    preview.append(f"... و {len(errors) - 12} خطای دیگر")
            if warnings:
                preview.extend(["", "هشدارهای تکراری (در صورت تأیید، وارد می‌شوند):"])
                preview.extend(warnings[:12])
                if len(warnings) > 12:
                    preview.append(f"... و {len(warnings) - 12} هشدار دیگر")
            preview.extend(["", "کد کالا از فایل خوانده می‌شود؛ شناسه داخلی خودکار ساخته می‌شود و موجودی اولیه صفر است."])
            if not rows:
                messagebox.showwarning("نتیجه بررسی فایل", "\n".join(preview), parent=parent)
                return
            if not messagebox.askyesno(
                "تأیید ورود کالاها",
                "\n".join(preview) + "\n\nفقط ردیف‌های معتبر وارد شوند؟",
                parent=parent,
            ):
                return
            imported = import_product_rows(self.ps, rows)
            reload_products()
            self.refresh()
            messagebox.showinfo(
                "ورود کامل شد",
                f"{imported} کالا با موفقیت وارد شد."
                + (f"\n{len(errors)} ردیف به دلیل خطای داده رد شد." if errors else "")
                + (f"\n{len(warnings)} هشدار تکراری با تأیید شما پذیرفته شد." if warnings else ""),
                parent=parent,
            )
        except Exception as exc:
            messagebox.showerror("خطا در ورود Excel", str(exc), parent=parent)

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
