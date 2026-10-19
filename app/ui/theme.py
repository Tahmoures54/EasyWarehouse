# -*- coding: utf-8 -*-
"""تم فیروزه‌ای آبی آسمان ایران."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

HEADER_BG = "#00838F"
BG = "#E3F2FD"
CARD_BG = "#FFFFFF"
CARD_BORDER = "#B3E5FC"
PRIMARY = "#0097A7"
PRIMARY_HOVER = "#00838F"
SECONDARY = "#42A5F5"
DANGER = "#EF5350"
TEXT = "#1A237E"
TEXT_MUTED = "#546E7A"
TABLE_HEADER = "#26C6DA"
ROW_ALT = "#E0F7FA"
ROW_WHITE = "#FFFFFF"
STOCK_CRIT = "#E53935"
STOCK_LOW = "#FB8C00"
STOCK_OK = "#43A047"
STATUS_BG = "#B2EBF2"
FONT = ("Tahoma", 10)
FONT_BOLD = ("Tahoma", 10, "bold")
FONT_TITLE = ("Tahoma", 14, "bold")


def apply_theme(root: tk.Tk) -> ttk.Style:
    """اعمال استایل ttk روی ریشه برنامه."""
    root.configure(bg=BG)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", font=FONT, foreground=TEXT, background=BG)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT, font=FONT)
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED, font=FONT)
    style.configure("Header.TFrame", background=HEADER_BG)
    style.configure("Header.TLabel", background=HEADER_BG, foreground="#FFFFFF", font=FONT_TITLE)
    style.configure("Version.TLabel", background=HEADER_BG, foreground="#E0F7FA", font=FONT)

    style.configure(
        "Card.TLabelframe",
        background=CARD_BG,
        foreground=TEXT,
        bordercolor=CARD_BORDER,
        relief="solid",
        borderwidth=1,
    )
    style.configure("Card.TLabelframe.Label", background=CARD_BG, foreground=TEXT, font=FONT_BOLD)

    style.configure("Primary.TButton", background=PRIMARY, foreground="#FFFFFF", font=FONT_BOLD, padding=6)
    style.map("Primary.TButton", background=[("active", PRIMARY_HOVER), ("pressed", PRIMARY_HOVER)])
    style.configure("Secondary.TButton", background=SECONDARY, foreground="#FFFFFF", font=FONT, padding=5)
    style.map("Secondary.TButton", background=[("active", "#1E88E5")])
    style.configure("Danger.TButton", background=DANGER, foreground="#FFFFFF", font=FONT, padding=5)
    style.map("Danger.TButton", background=[("active", "#E53935")])

    style.configure(
        "Treeview",
        background=ROW_WHITE,
        fieldbackground=ROW_WHITE,
        foreground=TEXT,
        rowheight=28,
        font=FONT,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=TABLE_HEADER,
        foreground="#FFFFFF",
        font=FONT_BOLD,
        relief="flat",
    )
    style.map("Treeview", background=[("selected", "#4DD0E1")], foreground=[("selected", TEXT)])

    style.configure("Status.TFrame", background=STATUS_BG)
    style.configure("Status.TLabel", background=STATUS_BG, foreground=TEXT, font=FONT)

    style.configure("TRadiobutton", background=CARD_BG, foreground=TEXT, font=FONT)
    style.configure("TEntry", fieldbackground="#FFFFFF", foreground=TEXT)
    style.configure("TCombobox", fieldbackground="#FFFFFF", foreground=TEXT)

    return style
