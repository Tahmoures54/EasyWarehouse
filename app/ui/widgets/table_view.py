# -*- coding: utf-8 -*-
"""جدول تراکنش‌ها."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Optional

from app.models.transaction import Transaction
from app.ui import theme as T


class TxTable(ttk.Frame):
    """Treeview تراکنش‌ها با رنگ نوع."""

    COLS = ("id", "date", "code", "name", "type", "qty", "unit", "note")
    HEADS = ("#", "تاریخ", "کد", "نام کالا", "نوع", "مقدار", "واحد", "توضیح")
    WIDTHS = (50, 95, 70, 170, 70, 70, 60, 160)

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)
        sb = ttk.Scrollbar(self)
        self.tree = ttk.Treeview(
            self,
            columns=self.COLS,
            show="headings",
            yscrollcommand=sb.set,
            height=12,
            selectmode="browse",
        )
        sb.config(command=self.tree.yview)
        for c, h, w in zip(self.COLS, self.HEADS, self.WIDTHS):
            self.tree.heading(c, text=h, anchor="center")
            self.tree.column(c, width=w, anchor="center", minwidth=40)
        self.tree.tag_configure("IN", foreground=T.STOCK_OK)
        self.tree.tag_configure("OUT", foreground=T.STOCK_CRIT)
        self.tree.tag_configure("RETURN", foreground=T.PRIMARY)
        self.tree.tag_configure("odd", background=T.ROW_ALT)
        self.tree.tag_configure("even", background=T.ROW_WHITE)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def load(self, items: List[Transaction]) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, t in enumerate(items):
            row_tag = "odd" if i % 2 else "even"
            self.tree.insert(
                "",
                tk.END,
                values=(t.id, t.date, t.code, t.name, t.type_fa(), f"{t.qty:g}", t.unit, t.note),
                tags=(t.type, row_tag),
            )

    def selected_id(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(self.tree.item(sel[0], "values")[0])
        except (IndexError, ValueError, TypeError):
            return None
