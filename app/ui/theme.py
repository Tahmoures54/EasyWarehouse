# -*- coding: utf-8 -*-
"""تم فیروزه‌ای آبی آسمان ایران."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

HEADER_BG = "#102A43"
BG = "#F3F6FB"
CARD_BG = "#FFFFFF"
CARD_BORDER = "#D9E2EF"
PRIMARY = "#087F8C"
PRIMARY_HOVER = "#066A75"
SECONDARY = "#E5EEF7"
DANGER = "#C2414B"
TEXT = "#172B4D"
TEXT_MUTED = "#60758B"
TABLE_HEADER = "#DCE8F2"
ROW_ALT = "#F4F8FC"
ROW_WHITE = "#FFFFFF"
STOCK_CRIT = "#DC2626"
STOCK_LOW = "#D97706"
STOCK_OK = "#15803D"
STATUS_BG = "#E7EEF6"
FONT = ("Tahoma", 10)
FONT_BOLD = ("Tahoma", 10, "bold")
FONT_TITLE = ("Tahoma", 17, "bold")


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
    style.configure("Header.TLabel", background=HEADER_BG, foreground="#FFFFFF", font=("Tahoma", 20, "bold"))
    style.configure("Header.Subtitle.TLabel", background=HEADER_BG, foreground="#C7D8E8", font=FONT)
    style.configure("Version.TLabel", background=HEADER_BG, foreground="#D6E4F0", font=FONT)
    style.configure("Section.TLabel", background=BG, foreground=TEXT, font=("Tahoma", 12, "bold"))
    style.configure("Metric.TFrame", background=CARD_BG, relief="solid", borderwidth=1)
    style.configure("MetricAccent.TFrame", background=PRIMARY)
    style.configure("MetricLabel.TLabel", background=CARD_BG, foreground=TEXT_MUTED, font=FONT)
    style.configure("MetricValue.TLabel", background=CARD_BG, foreground=TEXT, font=("Tahoma", 20, "bold"))
    style.configure("MetricHint.TLabel", background=CARD_BG, foreground=TEXT_MUTED, font=("Tahoma", 9))
    style.configure("Ghost.TButton", background=CARD_BG, foreground=TEXT, font=FONT, padding=(9, 6))
    style.map("Ghost.TButton", background=[("active", "#E5EEF7")], foreground=[("active", TEXT)])

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
