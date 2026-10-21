# -*- coding: utf-8 -*-
"""جدول تراکنش‌ها."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable, Optional, Sequence, Tuple

from app.models.transaction import Transaction
from app.ui import theme as T
from app.utils.date_utils import to_jalali


class TxTable(ttk.Frame):
    """Treeview تراکنش‌ها با رنگ نوع."""

    COLS = ("id", "date", "code", "name", "type", "qty", "unit", "note")
    HEADS = ("#", "تاریخ", "کد", "نام کالا", "نوع", "مقدار", "واحد", "توضیح")
    WIDTHS = (50, 95, 70, 170, 70, 70, 60, 160)
    # ستون‌های متنی راست‌چین (RTL)، ستون‌های عددی/کد وسط‌چین
    ALIGNS = ("center", "center", "center", "e", "center", "center", "center", "e")

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._items: Tuple[Transaction, ...] = ()
        self._query: str = ""

        self.scrollbar = ttk.Scrollbar(self)
        self.tree = ttk.Treeview(
            self,
            columns=self.COLS,
            show="headings",
            yscrollcommand=self.scrollbar.set,
            height=12,
            selectmode="browse",
        )
        self.scrollbar.config(command=self.tree.yview)

        for col, head, width, align in zip(
            self.COLS, self.HEADS, self.WIDTHS, self.ALIGNS
        ):
            self.tree.heading(col, text=head, anchor="center")
            self.tree.column(col, width=width, anchor=align, minwidth=40)

        self.tree.tag_configure("IN", foreground=T.STOCK_OK)
        self.tree.tag_configure("OUT", foreground=T.STOCK_CRIT)
        self.tree.tag_configure("RETURN", foreground=T.PRIMARY)
        self.tree.tag_configure("odd", background=T.ROW_ALT)
        self.tree.tag_configure("even", background=T.ROW_WHITE)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # ------------------------------------------------------------------ public

    def load(self, items: Iterable[Transaction]) -> int:
        """جایگزینی کل داده‌ها. تعداد ردیف‌های نمایش‌داده‌شده برگردانده می‌شود."""
        self._items = tuple(items)
        return self._render(reset_scroll=True)

    def filter(self, query: str) -> int:
        """فیلتر ردیف‌ها بر اساس شناسه، تاریخ، کد، نام، نوع یا توضیح."""
        self._query = query.strip().casefold()
        return self._render(reset_scroll=True)

    def clear(self) -> None:
        """خالی‌کردن کامل جدول و حافظهٔ نهان داده."""
        self._items = ()
        self._query = ""
        self.tree.delete(*self.tree.get_children())

    def selected_id(self) -> Optional[int]:
        """شناسهٔ تراکنش انتخاب‌شده یا `None`."""
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return int(self.tree.item(selection[0], "values")[0])
        except (IndexError, ValueError, TypeError):
            return None

    @property
    def total_count(self) -> int:
        """تعداد کل تراکنش‌ها (بدون فیلتر)."""
        return len(self._items)

    @property
    def visible_count(self) -> int:
        """تعداد ردیف‌های در حال نمایش."""
        return len(self.tree.get_children())

    # ----------------------------------------------------------------- internal

    def _render(self, *, reset_scroll: bool = False) -> int:
        self.tree.delete(*self.tree.get_children())
        for index, tx in enumerate(self._iter_visible()):
            self.tree.insert(
                "",
                tk.END,
                values=self._row_values(tx),
                tags=self._row_tags(tx, index),
            )
        if reset_scroll:
            self.tree.yview_moveto(0.0)
        return self.visible_count

    def _iter_visible(self) -> Iterable[Transaction]:
        if not self._query:
            yield from self._items
            return
        needle = self._query
        for tx in self._items:
            if needle in self._search_blob(tx):
                yield tx

    def _search_blob(self, tx: Transaction) -> str:
        return " ".join((
            str(tx.id),
            str(tx.date),
            _display_date(tx.date),
            str(tx.user_code or tx.code or ""),
            tx.name or "",
            tx.type_fa(),
            f"{tx.qty:g}",
            tx.unit or "",
            tx.note or "",
        )).casefold()

    @staticmethod
    def _row_values(tx: Transaction) -> tuple:
        return (
            tx.id,
            _display_date(tx.date),
            tx.user_code or tx.code or "",
            tx.name or "",
            tx.type_fa(),
            f"{tx.qty:g}",
            tx.unit or "",
            tx.note or "",
        )

    @staticmethod
    def _row_tags(tx: Transaction, index: int) -> Tuple[str, ...]:
        # ترتیب مهم است: در ttk.Treeview هر صفت با «آخرین تگِ تعریف‌کننده» بازنویسی می‌شود.
        # IN/OUT/RETURN فقط foreground می‌دهند و odd/even فقط background؛ بنابراین
        # در حال حاضر تداخلی ندارند — اما اگر روزی به تگ‌های zebra هم foreground دادید،
        # باید ترتیب را برعکس کنید تا رنگ نوع پنهان نشود.
        zebra = "odd" if index % 2 else "even"
        return (tx.type, zebra)


def _display_date(value: str) -> str:
    """تاریخ ذخیره‌شدهٔ میلادی را برای نمایش به خورشیدی تبدیل می‌کند."""
    try:
        return to_jalali(value)
    except ValueError:
        return value
