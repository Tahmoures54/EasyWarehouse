# -*- coding: utf-8 -*-
"""تم فیروزه‌ای آبی آسمان ایران."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Final

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ palette

HEADER_BG: Final = "#102A43"
HEADER_FG: Final = "#FFFFFF"
HEADER_MUTED: Final = "#C7D8E8"
BG: Final = "#F3F6FB"
CARD_BG: Final = "#FFFFFF"
CARD_BORDER: Final = "#D9E2EF"
PRIMARY: Final = "#087F8C"
PRIMARY_HOVER: Final = "#066A75"
PRIMARY_SOFT: Final = "#4DD0E1"
SECONDARY: Final = "#E5EEF7"
SECONDARY_HOVER: Final = "#D4E2F0"
DANGER: Final = "#C2414B"
DANGER_HOVER: Final = "#E53935"
TEXT: Final = "#172B4D"
TEXT_MUTED: Final = "#60758B"
TABLE_HEADER: Final = "#DCE8F2"
ROW_ALT: Final = "#F4F8FC"
ROW_WHITE: Final = "#FFFFFF"
STOCK_CRIT: Final = "#DC2626"
STOCK_LOW: Final = "#D97706"
STOCK_OK: Final = "#15803D"
STATUS_BG: Final = "#E7EEF6"

# -------------------------------------------------------------------- fonts

FONT_FAMILY: Final = "Tahoma"
FONT: Final = (FONT_FAMILY, 10)
FONT_BOLD: Final = (FONT_FAMILY, 10, "bold")
FONT_SMALL: Final = (FONT_FAMILY, 9)
FONT_SECTION: Final = (FONT_FAMILY, 12, "bold")
FONT_TITLE: Final = (FONT_FAMILY, 17, "bold")
FONT_HEADER: Final = (FONT_FAMILY, 20, "bold")
FONT_METRIC: Final = (FONT_FAMILY, 20, "bold")

# ------------------------------------------------------------------ spacing

PADDING_BUTTON: Final = (10, 6)
PADDING_ENTRY: Final = (6, 4)
PADDING_TAB: Final = (14, 6)
ROW_HEIGHT: Final = 28

# --------------------------------------------------------------------- api


def apply_theme(root: tk.Misc) -> ttk.Style:
    """اعمال استایل ttk روی ریشهٔ برنامه. خروجی برای استفادهٔ بیشتر برگردانده می‌شود."""
    root.configure(bg=BG)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        logger.debug("clam theme unavailable; falling back to default")

    _configure_base(style)
    _configure_header(style)
    _configure_cards(style)
    _configure_buttons(style)
    _configure_inputs(style, root)
    _configure_treeview(style)
    _configure_notebook(style)
    _configure_scrollbar(style)
    _configure_status(style)
    return style


# --------------------------------------------------------------- internals


def _configure_base(style: ttk.Style) -> None:
    style.configure(".", font=FONT, foreground=TEXT, background=BG)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT, font=FONT)
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED, font=FONT)
    style.configure("Section.TLabel", background=BG, foreground=TEXT, font=FONT_SECTION)
    style.configure("TSeparator", background=CARD_BORDER)


def _configure_header(style: ttk.Style) -> None:
    style.configure("Header.TFrame", background=HEADER_BG)
    style.configure(
        "Header.TLabel",
        background=HEADER_BG,
        foreground=HEADER_FG,
        font=FONT_HEADER,
    )
    style.configure(
        "Header.Subtitle.TLabel",
        background=HEADER_BG,
        foreground=HEADER_MUTED,
        font=FONT,
    )
    style.configure(
        "Version.TLabel", background=HEADER_BG, foreground=HEADER_MUTED, font=FONT
    )


def _configure_cards(style: ttk.Style) -> None:
    style.configure(
        "Metric.TFrame",
        background=CARD_BG,
        relief="solid",
        borderwidth=1,
        bordercolor=CARD_BORDER,
    )
    style.configure("MetricAccent.TFrame", background=PRIMARY)
    style.configure(
        "MetricLabel.TLabel", background=CARD_BG, foreground=TEXT_MUTED, font=FONT
    )
    style.configure(
        "MetricValue.TLabel", background=CARD_BG, foreground=TEXT, font=FONT_METRIC
    )
    style.configure(
        "MetricHint.TLabel", background=CARD_BG, foreground=TEXT_MUTED, font=FONT_SMALL
    )
    style.configure(
        "Card.TLabelframe",
        background=CARD_BG,
        foreground=TEXT,
        bordercolor=CARD_BORDER,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "Card.TLabelframe.Label", background=CARD_BG, foreground=TEXT, font=FONT_BOLD
    )


def _configure_buttons(style: ttk.Style) -> None:
    # پایهٔ TButton — دکمه‌های بدون کلاس استایل به این تکیه می‌کنند
    style.configure("TButton", font=FONT, padding=PADDING_BUTTON)
    style.map(
        "TButton",
        background=[("disabled", SECONDARY), ("active", SECONDARY_HOVER)],
        foreground=[("disabled", TEXT_MUTED), ("active", TEXT)],
    )

    style.configure(
        "Primary.TButton",
        background=PRIMARY,
        foreground="#FFFFFF",
        font=FONT_BOLD,
        padding=PADDING_BUTTON,
    )
    style.map(
        "Primary.TButton",
        background=[
            ("disabled", SECONDARY),
            ("pressed", PRIMARY_HOVER),
            ("active", PRIMARY_HOVER),
        ],
        foreground=[("disabled", TEXT_MUTED)],
    )

    style.configure(
        "Secondary.TButton",
        background=SECONDARY,
        foreground=TEXT,
        font=FONT_BOLD,
        padding=PADDING_BUTTON,
    )
    style.map(
        "Secondary.TButton",
        background=[("disabled", BG), ("active", SECONDARY_HOVER)],
        foreground=[("disabled", TEXT_MUTED), ("active", TEXT)],
    )

    style.configure(
        "Danger.TButton",
        background=DANGER,
        foreground="#FFFFFF",
        font=FONT,
        padding=PADDING_BUTTON,
    )
    style.map(
        "Danger.TButton",
        background=[("disabled", SECONDARY), ("active", DANGER_HOVER)],
        foreground=[("disabled", TEXT_MUTED)],
    )

    style.configure(
        "Ghost.TButton",
        background=CARD_BG,
        foreground=TEXT,
        font=FONT,
        padding=PADDING_BUTTON,
    )
    style.map(
        "Ghost.TButton",
        background=[("active", SECONDARY), ("pressed", SECONDARY_HOVER)],
        foreground=[("active", TEXT)],
    )


def _configure_inputs(style: ttk.Style, root: tk.Misc) -> None:
    # --- Entry
    style.configure(
        "TEntry",
        fieldbackground=ROW_WHITE,
        foreground=TEXT,
        bordercolor=CARD_BORDER,
        lightcolor=CARD_BORDER,
        darkcolor=CARD_BORDER,
        padding=PADDING_ENTRY,
        relief="flat",
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", PRIMARY), ("disabled", CARD_BORDER)],
        lightcolor=[("focus", PRIMARY)],
        darkcolor=[("focus", PRIMARY)],
        fieldbackground=[("disabled", BG), ("readonly", BG)],
        foreground=[("disabled", TEXT_MUTED), ("readonly", TEXT_MUTED)],
    )

    # --- Combobox
    style.configure(
        "TCombobox",
        fieldbackground=ROW_WHITE,
        background=ROW_WHITE,
        foreground=TEXT,
        arrowcolor=TEXT,
        bordercolor=CARD_BORDER,
        lightcolor=CARD_BORDER,
        darkcolor=CARD_BORDER,
        padding=PADDING_ENTRY,
    )
    style.map(
        "TCombobox",
        bordercolor=[("focus", PRIMARY)],
        lightcolor=[("focus", PRIMARY)],
        darkcolor=[("focus", PRIMARY)],
        fieldbackground=[("readonly", ROW_WHITE), ("disabled", BG)],
        foreground=[("readonly", TEXT), ("disabled", TEXT_MUTED)],
        arrowcolor=[("disabled", TEXT_MUTED)],
    )

    # --- لیست کشویی Combobox (استایل ttk ندارد؛ از option database استفاده می‌شود)
    for option, value in (
        ("*TCombobox*Listbox.background", ROW_WHITE),
        ("*TCombobox*Listbox.foreground", TEXT),
        ("*TCombobox*Listbox.selectBackground", PRIMARY),
        ("*TCombobox*Listbox.selectForeground", "#FFFFFF"),
        ("*TCombobox*Listbox.font", FONT),
    ):
        try:
            root.option_add(option, value)
        except tk.TclError:
            logger.debug("option_add failed for %s", option)


def _configure_treeview(style: ttk.Style) -> None:
    style.configure(
        "Treeview",
        background=ROW_WHITE,
        fieldbackground=ROW_WHITE,
        foreground=TEXT,
        rowheight=ROW_HEIGHT,
        font=FONT,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=TABLE_HEADER,
        foreground=TEXT,           # ← رفع باگ کنتراست: سفید روی آبی روشن نامرئی بود
        font=FONT_BOLD,
        relief="flat",
        padding=(6, 4),
    )
    style.map(
        "Treeview",
        background=[("selected", PRIMARY_SOFT)],
        foreground=[("selected", TEXT)],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", SECONDARY)],
        relief=[("active", "flat")],
    )


def _configure_notebook(style: ttk.Style) -> None:
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=SECONDARY,
        foreground=TEXT_MUTED,
        padding=PADDING_TAB,
        font=FONT,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", CARD_BG), ("active", SECONDARY_HOVER)],
        foreground=[("selected", TEXT), ("active", TEXT)],
    )


def _configure_scrollbar(style: ttk.Style) -> None:
    style.configure(
        "TScrollbar",
        background=CARD_BORDER,
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=TEXT_MUTED,
        relief="flat",
    )
    style.map("TScrollbar", background=[("active", TEXT_MUTED)])


def _configure_status(style: ttk.Style) -> None:
    style.configure("Status.TFrame", background=STATUS_BG)
    style.configure("Status.TLabel", background=STATUS_BG, foreground=TEXT, font=FONT)
