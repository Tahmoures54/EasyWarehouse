# -*- coding: utf-8 -*-
"""پنجره درباره برنامه."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional
import webbrowser

from app.config import APP_NAME, APP_VERSION, APP_AUTHOR, APP_LICENSE, GITHUB_URL
from app.ui import theme as T


class AboutWindow(tk.Toplevel):
    """اطلاعات نسخه و سازنده."""

    def __init__(self, master: Optional[tk.Misc] = None) -> None:
        super().__init__(master)
        self.title("درباره برنامه")
        self.geometry("420x280")
        self.resizable(False, False)
        self.configure(bg=T.BG)
        if master:
            self.transient(master)
            self.grab_set()

        f = ttk.Frame(self, padding=20)
        f.pack(fill=tk.BOTH, expand=True)

        tk.Label(f, text=APP_NAME, font=T.FONT_TITLE, fg=T.TEXT, bg=T.BG).pack()
        tk.Label(f, text=f"نسخه {APP_VERSION}", font=T.FONT, fg=T.TEXT_MUTED, bg=T.BG).pack(pady=4)
        tk.Label(f, text=f"سازنده: {APP_AUTHOR}", font=T.FONT, fg=T.TEXT, bg=T.BG).pack(pady=2)
        tk.Label(f, text=f"لایسنس: {APP_LICENSE}", font=T.FONT, fg=T.TEXT, bg=T.BG).pack(pady=2)

        link = tk.Label(f, text=GITHUB_URL, font=T.FONT, fg=T.PRIMARY, bg=T.BG, cursor="hand2")
        link.pack(pady=10)
        link.bind("<Button-1>", lambda e: webbrowser.open(GITHUB_URL))

        ttk.Button(f, text="بستن", style="Primary.TButton", command=self.destroy).pack(pady=10)
