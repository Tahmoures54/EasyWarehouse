# -*- coding: utf-8 -*-
"""صفحهٔ خوش‌آمدگویی (Splash Screen)."""

from __future__ import annotations

import tkinter as tk
from typing import Optional

from app.ui import theme as T


class SplashWindow(tk.Tk):
    """صفحهٔ خوش‌آمدگویی بدون قاب با نوار پیشرفت متحرک.

    به‌عنوان ریشهٔ موقت Tk ساخته می‌شود، پس از پایان مدت تعیین‌شده
    (یا کلیک کاربر) خود را می‌بندد. پس از آن می‌توان بدون تداخل،
    ``MainWindow`` را (که خودش یک ``tk.Tk`` است) ساخت.
    """

    WIDTH = 520
    HEIGHT = 320
    ACCENT = "#4DD0E1"

    def __init__(
        self,
        app_name: str,
        version: str,
        duration_ms: int = 1500,
        on_close: Optional[callable] = None,
    ) -> None:
        super().__init__()
        self._app_name = app_name
        self._version = version
        self._duration_ms = max(200, duration_ms)
        self._on_close = on_close
        self._animation_id: Optional[str] = None
        self._close_job: Optional[str] = None

        # پیکربندی پنجره
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=T.HEADER_BG)

        self._build()
        self._center()
        self._bind_close()
        self.deiconify()

        # شروع انیمیشن و بستن خودکار
        self.after(50, self._animate)
        self._close_job = self.after(self._duration_ms, self._close)

    # ------------------------------------------------------------------ layout

    def _build(self) -> None:
        # نوار باریک بالا (لهجه)
        tk.Frame(self, bg=self.ACCENT, height=4).pack(fill=tk.X, side=tk.TOP)

        body = tk.Frame(self, bg=T.HEADER_BG)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Frame(body, bg=T.HEADER_BG, height=32).pack()

        tk.Label(
            body,
            text=self._app_name,
            font=("Tahoma", 28, "bold"),
            bg=T.HEADER_BG,
            fg="#FFFFFF",
        ).pack()

        tk.Label(
            body,
            text=f"نسخه {self._version}",
            font=("Tahoma", 10),
            bg=T.HEADER_BG,
            fg=T.HEADER_MUTED,
        ).pack(pady=(4, 0))

        tk.Frame(body, bg=T.HEADER_BG, height=18).pack()

        tk.Label(
            body,
            text=f"به {self._app_name} خوش آمدید",
            font=("Tahoma", 12, "bold"),
            bg=T.HEADER_BG,
            fg=self.ACCENT,
        ).pack()

        tk.Frame(body, bg=T.HEADER_BG, height=24).pack()

        # نوار پیشرفت (Canvas برای کنترل کامل رنگ‌ها روی تم تیره)
        self._progress_canvas = tk.Canvas(
            body,
            bg="#1E3A5F",
            height=6,
            highlightthickness=0,
            bd=0,
        )
        self._progress_canvas.pack(fill=tk.X, padx=80)
        self._progress_bar = self._progress_canvas.create_rectangle(
            0, 0, 0, 6, fill=self.ACCENT, outline="",
        )
        self._progress_offset = 0

        tk.Label(
            body,
            text="در حال راه‌اندازی...",
            font=("Tahoma", 9),
            bg=T.HEADER_BG,
            fg="#8899AA",
        ).pack(pady=(8, 0))

        tk.Frame(self, bg=self.ACCENT, height=4).pack(fill=tk.X, side=tk.BOTTOM)

    def _center(self) -> None:
        self.update_idletasks()
        w, h = self.WIDTH, self.HEIGHT
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _bind_close(self) -> None:
        # کلیک = پرش از انتظار
        self.bind("<Button-1>", lambda _e: self._close())
        self.bind("<Escape>", lambda _e: self._close())

    # --------------------------------------------------------------- animation

    def _animate(self) -> None:
        if not self._progress_canvas.winfo_exists():
            return
        width = max(self._progress_canvas.winfo_width(), 300)
        segment = width // 3
        self._progress_offset = (self._progress_offset + 6) % (width + segment)
        x1 = self._progress_offset - segment
        x2 = self._progress_offset
        self._progress_canvas.coords(self._progress_bar, x1, 0, x2, 6)
        self._animation_id = self.after(20, self._animate)

    # ------------------------------------------------------------------- close

    def _close(self) -> None:
        if self._animation_id is not None:
            self.after_cancel(self._animation_id)
            self._animation_id = None
        if self._close_job is not None:
            self.after_cancel(self._close_job)
            self._close_job = None
        try:
            self.destroy()
        finally:
            if self._on_close is not None:
                self._on_close()
