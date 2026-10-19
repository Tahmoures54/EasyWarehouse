# -*- coding: utf-8 -*-
"""پنجره درباره برنامه."""

from __future__ import annotations

import logging
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from typing import Optional

from app.config import (
    APP_AUTHOR,
    APP_LICENSE,
    APP_NAME,
    APP_VERSION,
    GITHUB_URL,
)
from app.ui import theme as T

logger = logging.getLogger(__name__)


class AboutWindow(tk.Toplevel):
    """اطلاعات نسخه و سازنده."""

    MIN_WIDTH = 420
    MIN_HEIGHT = 280

    def __init__(self, master: Optional[tk.Misc] = None) -> None:
        super().__init__(master)
        self._configure(master)
        self._build()
        self._bind_shortcuts()
        self._center_on(master)

    # ------------------------------------------------------------------ setup

    def _configure(self, master: Optional[tk.Misc]) -> None:
        self.title("درباره برنامه")
        self.resizable(False, False)
        self.configure(bg=T.BG)
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        if master is not None:
            self.transient(master)
            self.grab_set()

    def _bind_shortcuts(self) -> None:
        self.bind("<Escape>", lambda _e: self.destroy())

    def _center_on(self, master: Optional[tk.Misc]) -> None:
        # بعد از ساخت محتوا، اندازهٔ واقعی در دسترس است
        self.update_idletasks()
        width = max(self.winfo_reqwidth(), self.MIN_WIDTH)
        height = max(self.winfo_reqheight(), self.MIN_HEIGHT)

        if master is not None and master.winfo_width() > 1:
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 2
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")

    # ----------------------------------------------------------------- layout

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        self._label(frame, APP_NAME, font=T.FONT_TITLE, fg=T.TEXT).pack()
        self._label(
            frame, f"نسخه {APP_VERSION}", fg=T.TEXT_MUTED
        ).pack(pady=4)
        self._label(
            frame, f"سازنده: {APP_AUTHOR or '—'}", fg=T.TEXT
        ).pack(pady=2)
        self._label(
            frame, f"لایسنس: {APP_LICENSE or '—'}", fg=T.TEXT
        ).pack(pady=2)

        self.link = self._label(
            frame, GITHUB_URL, fg=T.PRIMARY, cursor="hand2"
        )
        self.link.pack(pady=10)
        self.link.bind("<Button-1>", self._open_link)
        self.link.bind("<Enter>", lambda _e: self.link.configure(font=T.FONT_UNDERLINE))
        self.link.bind("<Leave>", lambda _e: self.link.configure(font=T.FONT))

        close_btn = ttk.Button(
            frame, text="بستن", style="Primary.TButton", command=self.destroy
        )
        close_btn.pack(pady=10)
        self.after_idle(close_btn.focus_set)

    def _label(
        self,
        parent: tk.Misc,
        text: str,
        *,
        font=None,
        fg=T.TEXT,
        cursor: str = "",
    ) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            font=font or T.FONT,
            fg=fg,
            bg=T.BG,
            cursor=cursor,
        )

    # ------------------------------------------------------------------ link

    def _open_link(self, _event: Optional[tk.Event] = None) -> str:
        try:
            opened = webbrowser.open(GITHUB_URL)
        except Exception:  # noqa: BLE001 — مرورگر ممکن است هر خطایی بدهد
            logger.exception("Failed to open GitHub URL")
            opened = False
        if not opened:
            messagebox.showwarning(
                "باز کردن لینک",
                f"امکان باز کردن مرورگر نبود.\nآدرس:\n{GITHUB_URL}",
                parent=self,
            )
        return "break"
