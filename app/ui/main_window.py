# -*- coding: utf-8 -*-
"""پنجره اصلی برنامه."""

from __future__ import annotations

import logging
import tkinter as tk
import webbrowser
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
from app.services.print_service import print_transaction
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

        self.withdraw()
        from app.services.user_service import UserService
        from app.ui.login_dialog import LoginDialog

        try:
            self.users = UserService(self.db)
            login = LoginDialog(self, self.users)
            self.wait_window(login)
            if login.user is None:
                self.destroy()
                return
            self.current_user = login.user
        except Exception as exc:
            logger.exception("Authentication initialization failed")
            # The root is withdrawn during login. Raise it before showing a
            # parented error dialog, otherwise the error can remain hidden.
            try:
                self.deiconify()
                self.lift()
                self.update_idletasks()
            except tk.TclError:
                logger.debug("Could not raise root to show startup error", exc_info=True)
            messagebox.showerror("خطای ورود", str(exc), parent=self)
            self.destroy()
            return

        self._init_services()
        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()
        self.deiconify()
        self.refresh()

    # ------------------------------------------------------------------ setup

    def _init_services(self) -> None:
        self.ps = ProductService(self.db)
        self.ts = TransactionService(self.db)
        self.backup = BackupService()
        self.reports = ReportService(self.db)

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
        prod_m.add_command(
            label="فهرست و کدگذاری کالا",
            command=self._list_products,
        )
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
        report_m.add_command(
            label="گزارش کالاهای راکد با موجودی (CSV)...",
            command=self._export_stale_inventory_report,
        )
        report_m.add_command(
            label="برگه شمارش فیزیکی موجودی (CSV)...",
            command=self._export_inventory_count_template,
        )
        report_m.add_command(
            label="ثبت شمارش و تعدیل موجودی...",
            command=self._open_stock_adjustment,
        )
        report_m.add_command(
            label="کاردکس کالا...",
            command=self._open_kardex,
        )
        report_m.add_separator()
        report_m.add_command(
            label="چاپ رسید / حواله گردش انتخاب‌شده...",
            command=self._print_selected_transaction,
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

        if self.current_user["role"] == "admin":
            users_m = tk.Menu(menubar, tearoff=0)
            users_m.add_command(label="مدیریت کاربران و گزارش امنیتی...", command=self._manage_users)
            menubar.add_cascade(label="مدیریت", menu=users_m)

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
        logo_line = ttk.Frame(title_box, style="Header.TFrame")
        logo_line.pack(anchor="w")
        self.logo_led = tk.Canvas(logo_line, width=22, height=22, bg=T.HEADER_BG, highlightthickness=0, bd=0)
        self.logo_led.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(logo_line, text="EasyWarehouse", style="Header.TLabel").pack(side=tk.LEFT)
        self._logo_pulse = 0
        self._animate_logo()
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
        role_label = {"admin": "مدیر", "operator": "انباردار", "viewer": "مشاهده‌گر"}.get(self.current_user["role"], self.current_user["role"])
        ttk.Label(
            head_right,
            text=f"کاربر: {self.current_user['display_name']}  |  نقش: {role_label}",
            style="Header.Subtitle.TLabel",
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
            text="↔  ثبت تراکنش انبار",
            style="Primary.TButton",
            command=self._open_transaction_form,
        ).pack(side=tk.LEFT, padx=(0, 7), ipady=3)
        ttk.Button(
            quick,
            text="⇩  خروجی گزارش موجودی",
            style="Secondary.TButton",
            command=self._export_inventory_report,
        ).pack(side=tk.LEFT, padx=(0, 7), ipady=3)
        ttk.Label(
            quick, text="جست‌وجوی گردش‌ها: Ctrl+F", style="Muted.TLabel"
        ).pack(side=tk.RIGHT)

    def _open_transaction_form(self) -> None:
        """فرم ثبت تراکنش را در یک پنجره مستقل باز می‌کند."""
        if not self._require_role("admin", "operator", action="ثبت تراکنش"):
            return
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
            win,
            self.ps,
            self.ts,
            on_ok=self._after_transaction_saved,
            on_manage_products=self._list_products,
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
            text="چاپ رسید / حواله",
            style="Primary.TButton",
            command=self._print_selected_transaction,
        ).pack(side=tk.LEFT, padx=(0, 6))
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
        """نوار وضعیت شامل وضعیت برنامه، مسیر دیتابیس و معرفی کوتاه توسعه‌دهنده."""
        status = ttk.Frame(self, style="Status.TFrame", padding=(10, 5))
        status.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_var = tk.StringVar(value="آماده")
        ttk.Label(
            status, textvariable=self.status_var, style="Status.TLabel"
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(
            status, text="ذخیره‌سازی محلی و خودکار", style="Status.TLabel"
        ).pack(side=tk.RIGHT, padx=(10, 0))

        # مسیر واقعی مورد استفاده برنامه؛ در صورت طولانی بودن، متن قابل انتخاب نیست
        # اما مسیر کامل در خود نوار وضعیت باقی می‌ماند.
        database_box = ttk.Frame(status, style="Status.TFrame")
        database_box.pack(side=tk.RIGHT, padx=(0, 10))
        ttk.Label(
            database_box,
            text=f"پایگاه داده: {get_db_path()}",
            style="Status.TLabel",
        ).pack(side=tk.RIGHT)

        # چراغ کوچک چشمک‌زن برای ایجاد حس پویایی؛ تزئینی است و وضعیت اتصال DB را
        # ادعا نمی‌کند.
        self.activity_led = tk.Canvas(
            database_box,
            width=14,
            height=14,
            highlightthickness=0,
            bd=0,
            bg=self._status_background(),
        )
        self.activity_led.pack(side=tk.RIGHT, padx=(7, 4))
        self._activity_led_on = False
        self._animate_activity_led()

        developer_ad = ttk.Label(
            status,
            text="طراحی و توسعه نرم‌افزار | تماس: 0916 068 4552",
            style="Status.TLabel",
            cursor="hand2",
        )
        developer_ad.pack(side=tk.RIGHT, padx=(0, 12))
        developer_ad.bind(
            "<Button-1>",
            lambda _event: self._contact_developer(),
        )
        developer_ad.bind(
            "<Enter>",
            lambda _event: developer_ad.configure(foreground=T.PRIMARY),
        )
        developer_ad.bind(
            "<Leave>",
            lambda _event: developer_ad.configure(foreground=""),
        )

    @staticmethod
    def _status_background() -> str:
        """رنگ پس‌زمینه نوار وضعیت را از تم فعال می‌گیرد."""
        return getattr(T, "STATUS_BG", getattr(T, "BG", "#F3F6F8"))

    def _animate_activity_led(self) -> None:
        """چراغ ظریف چشمک‌زن کنار مسیر دیتابیس."""
        try:
            if not self.winfo_exists() or not hasattr(self, "activity_led"):
                return
            self.activity_led.delete("all")
            color = "#16A34A" if self._activity_led_on else "#86EFAC"
            self.activity_led.create_oval(
                2, 2, 12, 12, fill=color, outline=color
            )
            self._activity_led_on = not self._activity_led_on
            self.after(650, self._animate_activity_led)
        except tk.TclError:
            # هنگام بسته شدن پنجره ممکن است callback بعدی دیگر لازم نباشد.
            return

    @staticmethod
    def _contact_developer() -> None:
        """راه تماس را باز می‌کند؛ شماره نیز برای تماس دستی نمایش داده می‌شود."""
        try:
            webbrowser.open("https://wa.me/989160684552")
        except Exception:
            logger.exception("Could not open developer contact link")

    def _animate_logo(self) -> None:
        """نشانگر تپندهٔ کنار لوگو؛ جلوه‌ای بصری و مستقل از وضعیت دیتابیس."""
        try:
            if not self.winfo_exists() or not hasattr(self, "logo_led"):
                return
            self.logo_led.delete("all")
            radius = 5 + (self._logo_pulse % 3)
            color = "#4DD0E1" if self._logo_pulse % 2 == 0 else "#80DEEA"
            self.logo_led.create_oval(11-radius, 11-radius, 11+radius, 11+radius, fill=color, outline=color)
            self._logo_pulse += 1
            self.after(420, self._animate_logo)
        except tk.TclError:
            return

    def _after_transaction_saved(self) -> None:
        """ثبت موفقیت تراکنش در دفتر حسابرسی و تازه‌سازی داشبورد."""
        self.users.log_event(
            self.current_user["username"],
            "inventory_transaction_saved",
            "تراکنش انبار با موفقیت ثبت شد",
        )
        self.refresh()

    def _manage_users(self) -> None:
        """باز کردن مدیریت کاربران فقط برای مدیر."""
        if not self._require_role("admin", action="مدیریت کاربران"):
            return
        from app.ui.user_management_dialog import UserManagementDialog
        UserManagementDialog(self, self.users, self.current_user["username"])

    def _require_role(self, *roles: str, action: str = "این عملیات") -> bool:
        """کنترل نقش در نقطهٔ اجرای عملیات، نه فقط پنهان‌کردن دکمه."""
        if self.current_user["role"] in roles:
            return True
        messagebox.showwarning("دسترسی محدود", f"نقش فعلی شما اجازهٔ انجام «{action}» را ندارد.", parent=self)
        self.users.log_event(self.current_user["username"], "permission_denied", action)
        return False

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
        if not self._require_role("admin", "operator", action="ثبت کالا"):
            return
        ProductForm(self, self.ps, on_save=self.refresh)

    def _list_products(self) -> None:
        if self._win_alive(self._products_win):
            self._products_win.lift()
            self._products_win.focus_force()
            return
        self._products_win = self._create_product_list_window()

    def _create_product_list_window(self) -> tk.Toplevel:
        win = tk.Toplevel(self)
        win.title("فهرست و کدگذاری کالا")
        win.geometry("1040x520")
        win.minsize(960, 460)
        win.configure(bg=T.BG)

        search_var = tk.StringVar()
        searchbar = ttk.Frame(win)
        searchbar.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(searchbar, text="جست‌وجوی فهرست (نام یا کد):").pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Entry(searchbar, textvariable=search_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        # ثبت کالا از همین بخش انجام می‌شود؛ ابتدا کد تجاری بررسی می‌شود.
        codebar = ttk.Frame(win)
        codebar.pack(fill=tk.X, padx=10, pady=(8, 0))
        ttk.Label(codebar, text="کد کالا برای بررسی/ثبت:").pack(
            side=tk.LEFT, padx=(0, 6)
        )
        entry_code_var = tk.StringVar()
        code_entry = ttk.Entry(codebar, textvariable=entry_code_var, width=24)
        code_entry.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(
            codebar,
            text="اگر کد موجود باشد، کالای ثبت‌شده انتخاب می‌شود.",
            style="Muted.TLabel",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # جدول پس از نوارهای جست‌وجو ساخته می‌شود تا آن‌ها در پنجره قابل مشاهده بمانند.
        tree = self._build_product_tree(win)

        def reload_and_refresh() -> None:
            self._reload_product_tree(tree, search_var.get())
            self.users.log_event(
                self.current_user["username"],
                "product_catalog_changed",
                "فهرست کالاها تغییر کرد",
            )
            self.refresh()

        def load() -> None:
            self._reload_product_tree(tree, search_var.get())

        def edit_selected() -> None:
            if not self._require_role("admin", "operator", action="ویرایش کالا"):
                return
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

        def find_or_add_by_code() -> None:
            """کد موجود را انتخاب کن؛ در غیر این صورت فرم ثبت را با کد باز کن."""
            if not self._require_role("admin", "operator", action="ثبت کالا"):
                return
            user_code = entry_code_var.get().strip()
            if not user_code:
                messagebox.showinfo(
                    "کد کالا",
                    "ابتدا کد کالا را وارد کنید.",
                    parent=win,
                )
                code_entry.focus_set()
                return

            try:
                matches = self.ps.get_by_user_code(user_code)
            except Exception as exc:
                logger.exception("Product code lookup failed")
                messagebox.showerror("خطا در جست‌وجوی کد", str(exc), parent=win)
                return

            if matches:
                self._reload_product_tree(tree, search_var.get())
                # اگر جست‌وجوی عمومی فعال است و کد در آن نیست، فیلتر را روی کد بگذار.
                if not tree.exists(matches[0].code):
                    search_var.set(user_code)
                    self._reload_product_tree(tree, user_code)
                if tree.exists(matches[0].code):
                    tree.selection_set(matches[0].code)
                    tree.focus(matches[0].code)
                    tree.see(matches[0].code)
                names = "\n".join(
                    f"• {item.name} (شناسه داخلی: {item.code})"
                    for item in matches[:5]
                )
                messagebox.showinfo(
                    "کد قبلاً ثبت شده است",
                    f"برای کد «{user_code}» کالا در فهرست وجود دارد؛ ثبت تکراری انجام نشد.\n\n{names}",
                    parent=win,
                )
                return

            ProductForm(
                win,
                self.ps,
                on_save=reload_and_refresh,
                initial_user_code=user_code,
            )

        code_entry.bind("<Return>", lambda _e: find_or_add_by_code())

        def delete_selected() -> None:
            if not self._require_role("admin", action="حذف کالا"):
                return
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
            text="ثبت کالای جدید",
            style="Primary.TButton",
            command=find_or_add_by_code,
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
        if not self._require_role("admin", "operator", action="ورود کالا از Excel"):
            return
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

    def _print_selected_transaction(self) -> None:
        """چاپ رسید ورود/عودت یا حواله خروج برای گردش انتخاب‌شده."""
        tid = self.table.selected_id()
        if tid is None:
            messagebox.showwarning(
                "انتخاب گردش",
                "ابتدا یک گردش را از جدول انتخاب کنید.",
                parent=self,
            )
            return
        try:
            tx = self.ts.get(tid)
            if tx is None:
                messagebox.showerror(
                    "گردش یافت نشد",
                    "رکورد انتخاب‌شده دیگر در دیتابیس وجود ندارد؛ جدول را تازه کنید.",
                    parent=self,
                )
                return
            path = print_transaction(tx, self.current_user.get("display_name", ""))
            self.users.log_event(
                self.current_user["username"],
                "inventory_voucher_printed",
                f"چاپ سند EW-{int(tx.id):06d} نوع {tx.type}",
            )
            messagebox.showinfo(
                "سند آماده چاپ است",
                "سند در مرورگر پیش‌فرض باز شد و پنجره چاپ باید نمایش داده شود.\n"
                "برای چاپ کاغذی، چاپگر را انتخاب کنید؛ برای فایل، گزینه Save as PDF را بزنید.\n\n"
                f"نسخه HTML نیز ذخیره شد:\n{path}",
                parent=self,
            )
        except Exception as exc:
            logger.exception("Transaction voucher printing failed")
            messagebox.showerror("خطا در چاپ سند", str(exc), parent=self)

    def _del_tx(self) -> None:
        if not self._require_role("admin", action="حذف گردش"):
            return
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
        if not self._require_role("admin", action="پشتیبان‌گیری"):
            return
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
        if not self._require_role("admin", action="بازیابی دیتابیس"):
            return
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
        from app.services.user_service import UserService
        self.users = UserService(self.db)
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

    def _open_stock_adjustment(self) -> None:
        """ثبت شمارش فیزیکی و تعدیل قابل ردیابی موجودی."""
        if not self._require_role("admin", "operator", action="ثبت تعدیل موجودی"):
            return
        from app.ui.stock_adjustment_dialog import StockAdjustmentDialog
        StockAdjustmentDialog(self, self.ps, self.db, self.current_user, on_saved=self.refresh)

    def _open_kardex(self) -> None:
        """نمایش گردش کامل و مانده تجمعی یک کالا."""
        from app.ui.kardex_window import KardexWindow

        KardexWindow(self, self.ps, self.reports)

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

    def _export_stale_inventory_report(self) -> None:
        self._save_report(
            "گزارش کالاهای راکد با موجودی",
            "stale-inventory.csv",
            lambda p: self.reports.export_stale_inventory_csv(p, days=90),
        )

    def _export_inventory_count_template(self) -> None:
        self._save_report(
            "برگه شمارش فیزیکی موجودی",
            "inventory-count.csv",
            lambda p: self.reports.export_inventory_count_template_csv(p),
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
