# -*- coding: utf-8 -*-
"""پنجره اصلی برنامه."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Optional

from app.config import (
    APP_GEOMETRY,
    APP_MIN_SIZE,
    APP_TITLE,
    APP_VERSION,
    ICON_PATH,
    get_db_path,
)
from app.database.db_manager import DB, DatabaseError
from app.services.backup_service import BackupService
from app.services.product_service import ProductService
from app.services.report_service import ReportService
from app.services.transaction_service import TransactionService
from app.ui import theme as T
from app.ui.about_window import AboutWindow
from app.ui.forms.product_form import ProductForm
from app.ui.forms.transaction_form import TransactionForm
from app.ui.help_window import HelpWindow
from app.ui.theme import apply_theme
from app.ui.widgets.table_view import TxTable

logger = logging.getLogger(__name__)

# سقف ردیف‌های بارگذاری‌شده در جدول (برای کارایی)
_TX_LOAD_LIMIT = 300
# سقف آیتم‌های لیست هشدار
_LOW_LIST_LIMIT = 60


class MainWindow(tk.Tk):
    """رابط اصلی مدیریت انبار."""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_GEOMETRY)
        self.minsize(*APP_MIN_SIZE)
        apply_theme(self)
        self._set_icon()

        self._help_win: Optional[HelpWindow] = None
        self._about_win: Optional[AboutWindow] = None
        self._products_win: Optional[tk.Toplevel] = None
        self._transaction_win: Optional[tk.Toplevel] = None
        self.form: Optional[TransactionForm] = None

        try:
            self.db = DB()
        except DatabaseError as exc:
            logger.exception("Database init failed")
            messagebox.showerror("خطای دیتابیس", str(exc), parent=self)
            self.destroy()
            return

        self._init_services()
        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()
        self.refresh()

    # ------------------------------------------------------------------ setup

    def _init_services(self) -> None:
        self.ps = ProductService(self.db)
        self.ts = TransactionService(self.db)
        self.backup = BackupService()
        self.reports = ReportService(self.db)
        self._seed_defaults_if_needed()

    def _seed_defaults_if_needed(self) -> None:
        """درج کالاهای پیش‌فرض در اولین اجرا (یا پس از بازیابی خالی).

        اگر ماژول seed در دسترس نباشد یا خطا بدهد، برنامه بی‌وقفه ادامه
        می‌دهد — Seed یک ویژگی اختیاری است، نه پیش‌نیاز.
        """
        try:
            from app.services.seed import seed_if_empty
        except ImportError:
            logger.debug("Seed module not available; skipping.")
            return
        try:
            inserted = seed_if_empty(self.db)
            if inserted:
                logger.info("Seeded %d default products on first run", inserted)
        except Exception:
            logger.exception("Seeding default products failed")

    def _set_icon(self) -> None:
        try:
            if ICON_PATH.exists():
                self.iconbitmap(str(ICON_PATH))
        except tk.TclError:
            logger.debug("iconbitmap failed for %s", ICON_PATH, exc_info=True)

    def _bind_shortcuts(self) -> None:
        self.bind("<F1>", lambda _e: self._help())
        self.bind("<Control-f>", self._focus_transaction_search)
        self.bind("<Control-F>", self._focus_transaction_search)

    # ------------------------------------------------------------------- menu

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
        report_m.add_command(
            label="گزارش وضعیت موجودی (CSV)...",
            command=self._export_inventory_report,
        )
        report_m.add_command(
            label="گزارش کمبود و ناموجودی (CSV)...",
            command=self._export_low_stock_report,
        )
        report_m.add_command(
            label="گزارش گردش تراکنش‌ها (CSV)...",
            command=self._export_transaction_report,
        )
        menubar.add_cascade(label="گزارش‌ها", menu=report_m)

        help_m = tk.Menu(menubar, tearoff=0)
        help_m.add_command(
            label="راهنمای کاربر", accelerator="F1", command=self._help
        )
        help_m.add_command(
            label="جست‌وجوی گردش‌ها", accelerator="Ctrl+F",
            command=self._focus_transaction_search,
        )
        help_m.add_separator()
        help_m.add_command(label="درباره برنامه", command=self._about)
        menubar.add_cascade(label="راهنما", menu=help_m)

        self.config(menu=menubar)

    # --------------------------------------------------------------------- ui

    def _build_ui(self) -> None:
        """داشبورد اصلی با اولویت عملیات پرتکرار و خوانایی سریع."""
        self.configure(bg=T.BG)
        self._build_header()
        self._build_metrics()
        self._build_quick_actions()
        self._build_workspace()
        self._build_status_bar()

    def _build_header(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame", padding=(22, 14))
        header.pack(fill=tk.X)
        header.grid_columnconfigure(0, weight=1)

        title_box = ttk.Frame(header, style="Header.TFrame")
        title_box.grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_box, text="EasyWarehouse", style="Header.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            text="مرکز کنترل موجودی و گردش کالا",
            style="Header.Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        head_right = ttk.Frame(header, style="Header.TFrame")
        head_right.grid(row=0, column=1, sticky="e")
        ttk.Label(
            head_right, text=f"نسخه {APP_VERSION}", style="Version.TLabel"
        ).pack(anchor="e")
        ttk.Label(
            head_right, text="داشبورد انبار", style="Header.Subtitle.TLabel"
        ).pack(anchor="e", pady=(4, 0))

    def _build_metrics(self) -> None:
        metrics = ttk.Frame(self, padding=(16, 12, 16, 4))
        metrics.pack(fill=tk.X)
        for col in range(4):
            metrics.columnconfigure(col, weight=1, uniform="metric")
        self.metric_products = self._metric_card(
            metrics, 0, "تعداد کالاها", "۰", "کالا در فهرست", "#087F8C"
        )
        self.metric_transactions = self._metric_card(
            metrics, 1, "گردش‌های ثبت‌شده", "۰", "ورود، خروج و عودت", "#2563EB"
        )
        self.metric_low = self._metric_card(
            metrics, 2, "نیازمند بررسی", "۰",
            "کمتر از حداقل یا ناموجود", "#D97706",
        )
        self.metric_zero = self._metric_card(
            metrics, 3, "ناموجود", "۰",
            "موجودی صفر یا کمتر", "#DC2626",
        )

    def _metric_card(
        self,
        parent: ttk.Frame,
        column: int,
        title: str,
        value: str,
        hint: str,
        accent: str,
    ) -> ttk.Label:
        card = ttk.Frame(parent, style="Metric.TFrame", padding=(14, 10))
        card.grid(row=0, column=column, sticky="nsew", padx=5, pady=2)
        # رنگ لهجه در هر کارت متفاوت است؛ به همین دلیل tk.Frame خام
        # به‌جای استایل ttk استفاده می‌شود.
        tk.Frame(card, bg=accent, height=4).pack(fill=tk.X, pady=(0, 7))
        ttk.Label(card, text=title, style="MetricLabel.TLabel").pack(anchor="w")
        value_label = ttk.Label(card, text=value, style="MetricValue.TLabel")
        value_label.pack(anchor="w", pady=(3, 0))
        ttk.Label(card, text=hint, style="MetricHint.TLabel").pack(
            anchor="w", pady=(2, 0)
        )
        return value_label

    def _build_quick_actions(self) -> None:
        quick = ttk.Frame(self, padding=(16, 5, 16, 10))
        quick.pack(fill=tk.X)
        ttk.Label(quick, text="عملیات سریع", style="Section.TLabel").pack(
            side=tk.LEFT, padx=(0, 12)
        )
        ttk.Button(
            quick,
            text="▦  فهرست و کدگذاری کالا",
            style="Primary.TButton",
            command=self._list_products,
        ).pack(side=tk.LEFT, padx=(0, 7), ipady=3)
        ttk.Button(
            quick,
            text="+  ثبت کالای جدید",
            style="Secondary.TButton",
            command=self._add_product,
        ).pack(side=tk.LEFT, padx=(0, 7), ipady=3)
        ttk.Button(
            quick,
            text="⇩  خروجی گزارش موجودی",
            style="Secondary.TButton",
            command=self._export_inventory_report,
        ).pack(side=tk.LEFT, padx=(0, 7), ipady=3)
        ttk.Button(
            quick,
            text="↔  ثبت تراکنش انبار",
            style="Primary.TButton",
            command=self._open_transaction_form,
        ).pack(side=tk.LEFT, padx=(0, 7), ipady=3)
        ttk.Label(
            quick, text="جست‌وجوی گردش‌ها: Ctrl+F", style="Muted.TLabel"
        ).pack(side=tk.RIGHT)

    def _open_transaction_form(self) -> None:
        """فرم ثبت تراکنش را در یک پنجره مستقل باز می‌کند."""
        if self._win_alive(self._transaction_win):
            self._transaction_win.lift()
            self._transaction_win.focus_force()
            if self.form is not None:
                self.form.refresh(None)
            return

        win = tk.Toplevel(self)
        self._transaction_win = win
        win.title("ثبت تراکنش انبار")
        win.geometry("620x430")
        win.minsize(580, 390)
        win.configure(bg=T.BG)
        win.transient(self)
        win.protocol("WM_DELETE_WINDOW", self._close_transaction_form)

        self.form = TransactionForm(
            win, self.ps, self.ts, on_ok=self.refresh
        )
        self.form.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        self.form.refresh(None)
        win.lift()
        win.focus_force()

    def _close_transaction_form(self) -> None:
        """پنجره فرم تراکنش را ببند و ارجاع‌های آن را آزاد کن."""
        win = self._transaction_win
        self._transaction_win = None
        self.form = None
        if self._win_alive(win):
            win.destroy()

    def _build_workspace(self) -> None:
        mid = ttk.Frame(self, padding=(16, 2, 16, 12))
        mid.pack(fill=tk.BOTH, expand=True)
        mid.columnconfigure(0, weight=4)
        mid.columnconfigure(1, weight=1, minsize=230)
        mid.rowconfigure(0, weight=1)

        self._build_transactions_panel(mid)
        self._build_warnings_panel(mid)

    def _build_transactions_panel(self, parent: ttk.Frame) -> None:
        left = ttk.LabelFrame(
            parent, text="  گردش کالاها  ", style="Card.TLabelframe", padding=10
        )
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        toolbar = ttk.Frame(left)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(toolbar, text="جست‌وجو", style="Muted.TLabel").pack(
            side=tk.LEFT, padx=(0, 7)
        )
        self.tx_search_var = tk.StringVar()
        self.transaction_search_entry = ttk.Entry(
            toolbar, textvariable=self.tx_search_var
        )
        self.transaction_search_entry.pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=4
        )
        self.transaction_search_entry.bind(
            "<KeyRelease>",
            lambda _e: self.table.filter(self.tx_search_var.get()),
        )
        self.transaction_search_entry.bind(
            "<Escape>", self._clear_transaction_search
        )
        ttk.Button(
            toolbar,
            text="پاک‌کردن",
            style="Ghost.TButton",
            command=self._clear_transaction_search,
        ).pack(side=tk.LEFT, padx=(6, 0))

        self.table = TxTable(left)
        self.table.pack(fill=tk.BOTH, expand=True)

        table_actions = ttk.Frame(left)
        table_actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(
            table_actions,
            text="حذف گردش انتخاب‌شده",
            style="Danger.TButton",
            command=self._del_tx,
        ).pack(side=tk.LEFT)
        ttk.Button(
            table_actions,
            text="تازه‌سازی",
            style="Ghost.TButton",
            command=self.refresh,
        ).pack(side=tk.LEFT, padx=6)

    def _build_warnings_panel(self, parent: ttk.Frame) -> None:
        right = ttk.LabelFrame(
            parent, text="  هشدارهای موجودی  ", style="Card.TLabelframe", padding=10
        )
        right.grid(row=0, column=1, sticky="nsew")
        ttk.Label(
            right,
            text="مواردی که بهتر است بررسی شوند",
            style="Muted.TLabel",
            wraplength=210,
        ).pack(anchor="w", pady=(0, 8))

        list_wrap = ttk.Frame(right)
        list_wrap.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(list_wrap)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.low_list = tk.Listbox(
            list_wrap,
            width=28,
            height=12,
            font=T.FONT,
            bg=T.CARD_BG,
            fg=T.TEXT,
            selectbackground=T.PRIMARY,
            selectforeground="#FFFFFF",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=T.CARD_BORDER,
            activestyle="none",
            yscrollcommand=scroll.set,
        )
        self.low_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.low_list.yview)

        ttk.Button(
            right,
            text="مشاهده فهرست کالاها",
            style="Secondary.TButton",
            command=self._list_products,
        ).pack(fill=tk.X, pady=(9, 0))

    def _build_status_bar(self) -> None:
        status = ttk.Frame(self, style="Status.TFrame", padding=(12, 6))
        status.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="آماده")
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel").pack(
            side=tk.LEFT
        )
        ttk.Label(
            status, text="ذخیره‌سازی محلی و خودکار", style="Status.TLabel"
        ).pack(side=tk.RIGHT, padx=(0, 12))
        ttk.Label(
            status, text=f"پایگاه داده: {get_db_path()}", style="Status.TLabel"
        ).pack(side=tk.RIGHT)

    # --------------------------------------------------------------- shortcuts

    def _focus_transaction_search(self, _event=None) -> str:
        self.transaction_search_entry.focus_set()
        self.transaction_search_entry.selection_range(0, tk.END)
        return "break"

    def _clear_transaction_search(self, _event=None) -> str:
        self.tx_search_var.set("")
        self.table.filter("")
        return "break"

    # ---------------------------------------------------------------- refresh

    def refresh(self) -> None:
        """به‌روزرسانی جدول، شاخص‌ها و هشدارها.

        هر بخش مستقل است: خطا در یک بخش، بقیه را متوقف نمی‌کند. خطاها در
        انتها یک‌جا گزارش می‌شوند تا کاربر از داده‌های قدیمی گمراه نشود.
        """
        errors: list[str] = []
        txs = []

        try:
            txs = self.ts.all(limit=_TX_LOAD_LIMIT)
            self.table.load(txs)
        except Exception as exc:
            logger.exception("Failed to load transactions")
            errors.append(f"جدول تراکنش‌ها: {exc}")

        if self.form is not None and self._win_alive(self._transaction_win):
            try:
                self.form.refresh(None)
            except Exception:
                logger.exception("Failed to refresh transaction form")
                errors.append("فرم ثبت تراکنش")

        try:
            all_products = self.ps.all()
            total_tx = self.ts.count()
            self._refresh_metrics(total_tx, all_products)
            self._refresh_low_list(all_products)
            self.status_var.set(
                f"آماده  |  نمایش {len(txs):,} از {total_tx:,} گردش"
                f"  |  {len(all_products):,} کالا"
            )
        except Exception:
            logger.exception("Failed to refresh metrics")
            errors.append("شاخص‌ها و هشدارها")

        if errors:
            messagebox.showwarning(
                "به‌روزرسانی ناقص",
                "برخی بخش‌ها به‌روزرسانی نشدند:\n\n"
                + "\n".join(f"• {item}" for item in errors),
                parent=self,
            )

    def _refresh_metrics(
        self, total_tx: int, all_products: list
    ) -> None:
        warns = sum(
            1 for p in all_products if p.is_warning() or p.is_empty()
        )
        empties = sum(1 for p in all_products if p.is_empty())
        self.metric_products.config(text=f"{len(all_products):,}")
        self.metric_transactions.config(text=f"{total_tx:,}")
        self.metric_low.config(text=f"{warns:,}")
        self.metric_zero.config(text=f"{empties:,}")

    def _refresh_low_list(self, all_products: list) -> None:
        # نکته: کالای با stock=0 و min_stock=0 نه is_low است نه is_critical،
        # ولی «ناموجود» است. به همین دلیل is_empty هم لحاظ می‌شود.
        issues = sorted(
            (
                p for p in all_products
                if p.is_warning() or p.is_empty()
            ),
            key=lambda p: (p.stock, p.name),
        )
        self.low_list.delete(0, tk.END)
        if not issues:
            self.low_list.insert(tk.END, "✓  وضعیت موجودی مناسب است")
            return
        for product in issues[:_LOW_LIST_LIMIT]:
            marker = "●" if product.is_critical() else "○"
            suffix = "  (ناموجود)" if product.is_empty() and not product.is_critical() else ""
            self.low_list.insert(
                tk.END,
                f"{marker}  {product.name}: {product.stock:g} {product.unit}{suffix}",
            )
        if len(issues) > _LOW_LIST_LIMIT:
            self.low_list.insert(
                tk.END,
                f"… و {len(issues) - _LOW_LIST_LIMIT} مورد دیگر",
            )

    # -------------------------------------------------------------- products

    def _add_product(self) -> None:
        ProductForm(self, self.ps, on_save=self.refresh)

    def _list_products(self) -> None:
        if self._win_alive(self._products_win):
            self._products_win.lift()
            self._products_win.focus_force()
            return
        self._products_win = self._create_product_list_window()

    def _create_product_list_window(self) -> tk.Toplevel:
        win = tk.Toplevel(self)
        win.title("کتابخانه کالاها")
        win.geometry("1040x520")
        win.minsize(960, 460)
        win.configure(bg=T.BG)

        tree = self._build_product_tree(win)

        search_var = tk.StringVar()
        searchbar = ttk.Frame(win)
        searchbar.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(searchbar, text="جست‌وجوی کالا (نام یا کد):").pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Entry(searchbar, textvariable=search_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        def reload_and_refresh() -> None:
            self._reload_product_tree(tree, search_var.get())
            self.refresh()

        def load() -> None:
            self._reload_product_tree(tree, search_var.get())

        def edit_selected() -> None:
            selection = tree.selection()
            if not selection:
                messagebox.showinfo(
                    "انتخاب کالا",
                    "لطفاً یک کالا را از فهرست انتخاب کنید.",
                    parent=win,
                )
                return
            product = self.ps.get(selection[0])
            if product is not None:
                ProductForm(
                    win, self.ps, product=product, on_save=reload_and_refresh
                )

        def delete_selected() -> None:
            selection = tree.selection()
            if not selection:
                messagebox.showinfo(
                    "انتخاب کالا",
                    "لطفاً یک کالا را از فهرست انتخاب کنید.",
                    parent=win,
                )
                return
            values = tree.item(selection[0], "values")
            if not messagebox.askyesno(
                "تأیید",
                f"حذف کالای {values[0]} - {values[1]}؟",
                parent=win,
            ):
                return
            try:
                self.ps.delete(selection[0])
            except Exception as exc:
                logger.exception("Delete product failed")
                messagebox.showerror("خطا", str(exc), parent=win)
                return
            reload_and_refresh()

        # دوبار کلیک روی ردیف = ویرایش
        tree.bind("<Double-1>", lambda _e: edit_selected())
        # Enter = ویرایش، Delete = حذف
        tree.bind("<Return>", lambda _e: edit_selected())
        tree.bind("<Delete>", lambda _e: delete_selected())

        search_var.trace_add("write", lambda *_args: load())

        buttons = ttk.Frame(win)
        buttons.pack(fill=tk.X, padx=10, pady=6)
        ttk.Button(
            buttons,
            text="جدید",
            style="Primary.TButton",
            command=lambda: ProductForm(
                win, self.ps, on_save=reload_and_refresh
            ),
        ).pack(side=tk.LEFT, padx=3)
        ttk.Button(
            buttons,
            text="ویرایش",
            style="Secondary.TButton",
            command=edit_selected,
        ).pack(side=tk.LEFT, padx=3)
        ttk.Button(
            buttons,
            text="حذف",
            style="Danger.TButton",
            command=delete_selected,
        ).pack(side=tk.LEFT, padx=3)
        ttk.Button(
            buttons,
            text="دریافت الگوی Excel",
            style="Secondary.TButton",
            command=lambda: self._download_product_template(win),
        ).pack(side=tk.LEFT, padx=3)
        ttk.Button(
            buttons,
            text="ورود از Excel",
            style="Primary.TButton",
            command=lambda: self._import_products_excel(win, reload_and_refresh),
        ).pack(side=tk.LEFT, padx=3)
        ttk.Button(buttons, text="بستن", command=win.destroy).pack(
            side=tk.RIGHT
        )

        load()
        return win

    @staticmethod
    def _build_product_tree(parent: tk.Misc) -> ttk.Treeview:
        columns = (
            ("code", "کد کالا", 110, "center"),
            ("name", "نام", 190, "e"),
            ("unit", "واحد", 55, "center"),
            ("cat", "دسته", 70, "center"),
            ("shelf", "قفسه", 90, "center"),
            ("min", "حداقل", 55, "center"),
            ("stock", "موجودی", 65, "center"),
        )
        tree = ttk.Treeview(
            parent, columns=[c[0] for c in columns], show="headings", height=14
        )
        for name, header, width, anchor in columns:
            tree.heading(name, text=header)
            tree.column(name, width=width, anchor=anchor)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))
        return tree

    def _reload_product_tree(self, tree: ttk.Treeview, query: str) -> None:
        tree.delete(*tree.get_children())
        needle = query.strip().casefold()
        for product in self.ps.all():
            haystack = (
                f"{product.user_code} {product.code} {product.name} "
                f"{product.category} {product.shelf or ''}"
            ).casefold()
            if needle and needle not in haystack:
                continue
            tree.insert(
                "",
                tk.END,
                iid=product.code,
                values=(
                    product.user_code or product.code,
                    product.name,
                    product.unit,
                    product.category,
                    product.shelf or "—",
                    f"{product.min_stock:g}",
                    f"{product.stock:g}",
                ),
            )

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _win_alive(win: Optional[tk.Misc]) -> bool:
        try:
            return win is not None and win.winfo_exists()
        except tk.TclError:
            return False

    # --------------------------------------------------------------- reports

    def _download_product_template(self, parent: tk.Misc) -> None:
        path = filedialog.asksaveasfilename(
            parent=parent,
            title="ذخیره الگوی ورود کالا",
            defaultextension=".xlsx",
            initialfile="easywarehouse-products-template.xlsx",
            filetypes=[("فایل Excel", "*.xlsx")],
        )
        if not path:
            return
        try:
            from app.services.product_excel_service import create_product_template

            create_product_template(path)
            messagebox.showinfo(
                "الگوی Excel آماده است",
                "فایل الگو ذخیره شد. کد و نام کالا را وارد کنید؛ تکراری بودن "
                "هرکدام هشدار می‌دهد اما با تأیید شما مانع ورود نیست. "
                "شناسه داخلی خودکار ساخته می‌شود و موجودی اولیه صفر خواهد بود.",
                parent=parent,
            )
        except Exception as exc:
            logger.exception("Template creation failed")
            messagebox.showerror("خطا در ساخت الگو", str(exc), parent=parent)

    def _import_products_excel(
        self, parent: tk.Misc, reload_products: Callable[[], None]
    ) -> None:
        path = filedialog.askopenfilename(
            parent=parent,
            title="انتخاب فایل Excel کالاها",
            filetypes=[("فایل Excel", "*.xlsx")],
        )
        if not path:
            return
        try:
            from app.services.product_excel_service import (
                import_product_rows,
                preview_product_import,
            )

            rows, errors, total_rows, warnings = preview_product_import(
                path, self.ps
            )
            if not rows and not errors:
                messagebox.showinfo(
                    "ورود کالا",
                    "فایل ردیف کالای قابل ورود ندارد.",
                    parent=parent,
                )
                return
            preview = [
                f"ردیف‌های قابل ورود: {len(rows)}",
                f"ردیف‌های ردشده: {len(errors)}",
                f"تعداد ردیف‌های بررسی‌شده: {total_rows}",
            ]
            if errors:
                preview.append("")
                preview.append("موارد نیازمند اصلاح:")
                preview.extend(errors[:12])
                if len(errors) > 12:
                    preview.append(f"... و {len(errors) - 12} خطای دیگر")
            if warnings:
                preview.append("")
                preview.append(
                    "هشدارهای تکراری (در صورت تأیید، وارد می‌شوند):"
                )
                preview.extend(warnings[:12])
                if len(warnings) > 12:
                    preview.append(f"... و {len(warnings) - 12} هشدار دیگر")
            preview.append("")
            preview.append(
                "کد کالا از فایل خوانده می‌شود؛ شناسه داخلی خودکار ساخته "
                "می‌شود و موجودی اولیه صفر است."
            )
            if not rows:
                messagebox.showwarning(
                    "نتیجه بررسی فایل", "\n".join(preview), parent=parent
                )
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
                + (
                    f"\n{len(errors)} ردیف به دلیل خطای داده رد شد."
                    if errors else ""
                )
                + (
                    f"\n{len(warnings)} هشدار تکراری با تأیید شما پذیرفته شد."
                    if warnings else ""
                ),
                parent=parent,
            )
        except Exception as exc:
            logger.exception("Excel import failed")
            messagebox.showerror("خطا در ورود Excel", str(exc), parent=parent)

    # ----------------------------------------------------------- transactions

    def _del_tx(self) -> None:
        tid = self.table.selected_id()
        if tid is None:
            messagebox.showwarning(
                "توجه", "یک ردیف را از جدول انتخاب کنید.", parent=self
            )
            return

        # خلاصهٔ تراکنش برای تأیید آگاهانه‌تر
        summary = f"حذف تراکنش شماره {tid}؟"
        try:
            tx = self.ts.get(tid)
            if tx is not None:
                summary = (
                    f"حذف تراکنش شماره {tid}؟\n\n"
                    f"{tx.type_fa()} به مقدار {tx.qty:g} {tx.unit or ''}\n"
                    f"کالا: {tx.name or tx.code}\n"
                    f"تاریخ: {tx.date}"
                )
        except Exception:
            logger.debug("Could not load tx details for confirmation", exc_info=True)

        if not messagebox.askyesno("تأیید", summary, parent=self):
            return
        try:
            self.ts.delete(tid)
            self.refresh()
        except Exception as exc:
            logger.exception("Delete transaction failed")
            messagebox.showerror("خطا", str(exc), parent=self)

    # ---------------------------------------------------------------- backup

    def _do_backup(self) -> None:
        dest = filedialog.askdirectory(
            title="انتخاب پوشه پشتیبان", parent=self
        )
        if not dest:
            return
        try:
            path = self.backup.backup(dest)
            messagebox.showinfo(
                "پشتیبان‌گیری", f"فایل ذخیره شد:\n{path}", parent=self
            )
        except Exception as exc:
            logger.exception("Backup failed")
            messagebox.showerror("خطا", str(exc), parent=self)

    def _do_restore(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="انتخاب فایل پشتیبان",
            filetypes=[
                ("Database", "*.db *.sqlite *.sqlite3"),
                ("All", "*.*"),
            ],
        )
        if not path:
            return
        if not messagebox.askyesno(
            "هشدار",
            "دیتابیس فعلی جایگزین می‌شود. ادامه می‌دهید؟",
            parent=self,
        ):
            return

        try:
            self.backup.restore(path)
        except Exception as exc:
            logger.exception("Restore failed")
            messagebox.showerror("خطا در بازیابی", str(exc), parent=self)
            return

        try:
            self._reload_after_restore()
        except Exception as exc:
            logger.exception("Reload after restore failed")
            messagebox.showerror(
                "خطا در بارگذاری مجدد",
                f"دیتابیس بازیابی شد اما بارگذاری مجدد ناموفق بود:\n{exc}\n\n"
                "لطفاً برنامه را یک بار ببندید و دوباره باز کنید.",
                parent=self,
            )
            return

        messagebox.showinfo(
            "بازیابی", "بازیابی با موفقیت انجام شد.", parent=self
        )

    def _reload_after_restore(self) -> None:
        """DB و سرویس‌ها را بازسازی می‌کند و UI را به آن‌ها وصل می‌کند."""
        old_db = getattr(self, "db", None)
        if old_db is not None:
            try:
                old_db.close()
            except Exception:
                logger.debug("Old DB close failed", exc_info=True)

        self.db = DB()
        self._init_services()  # در صورت خالی بودن DB جدید، seed اجرا می‌شود

        # اگر فرم ثبت تراکنش باز است، آن را ببند تا به سرویس‌های جدید وصل شود.
        if self._win_alive(self._transaction_win):
            self._transaction_win.destroy()
        self._transaction_win = None
        self.form = None

        # پنجرهٔ کالاها (اگر باز است) با سرویس‌های قدیمی کار می‌کرد
        if self._win_alive(self._products_win):
            self._products_win.destroy()
        self._products_win = None

        self.refresh()

    # --------------------------------------------------------------- reports

    def _export_inventory_report(self) -> None:
        self._save_report(
            "گزارش موجودی",
            "inventory.csv",
            lambda p: self.reports.export_inventory_csv(p),
        )

    def _export_low_stock_report(self) -> None:
        self._save_report(
            "گزارش کمبود موجودی",
            "low-stock.csv",
            lambda p: self.reports.export_inventory_csv(p, low_only=True),
        )

    def _export_transaction_report(self) -> None:
        self._save_report(
            "گزارش گردش تراکنش‌ها",
            "transactions.csv",
            lambda p: self.reports.export_transactions_csv(p),
        )

    def _save_report(
        self, title: str, filename: str, exporter: Callable[[str], Path]
    ) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            title=title,
            defaultextension=".csv",
            initialfile=filename,
            filetypes=[("CSV سازگار با Excel", "*.csv")],
        )
        if not path:
            return
        try:
            saved = exporter(path)
            messagebox.showinfo(
                title, f"گزارش ذخیره شد:\n{saved}", parent=self
            )
        except Exception as exc:
            logger.exception("Report export failed")
            messagebox.showerror(
                "خطا در تهیه گزارش", str(exc), parent=self
            )

    # ----------------------------------------------------------- help/about

    def _help(self) -> None:
        if self._win_alive(self._help_win):
            self._help_win.lift()
            self._help_win.focus_force()
            return
        self._help_win = HelpWindow(self)

    def _about(self) -> None:
        if self._win_alive(self._about_win):
            self._about_win.lift()
            self._about_win.focus_force()
            return
        self._about_win = AboutWindow(self)
