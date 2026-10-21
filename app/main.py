# -*- coding: utf-8 -*-
"""نقطه ورود انبارداری آسان.

اجرا:
    python -m app.main
    python -m app.main --no-splash
    python -m app.main --version
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# --- اطمینان از حضور ریشه پروژه در sys.path (فقط هنگام اجرا به‌عنوان اسکریپت) ---
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger(__name__)


# --------------------------------------------------------------- bootstrap


def _enable_dpi_awareness() -> None:
    """فعال‌سازی رندر HiDPI روی ویندوز (بدون اثر روی سایر سیستم‌ها)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
    except ImportError:
        return

    attempts = (
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2),  # per-monitor v1
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(1),  # system
        lambda: ctypes.windll.user32.SetProcessDPIAware(),       # legacy
    )
    for call in attempts:
        try:
            call()
            return
        except (AttributeError, OSError):
            continue


def _setup_logging(verbose: bool = False) -> Optional[Path]:
    """پیکربندی لاگ به فایل و (در صورت وجود ترمینال) به stderr."""
    try:
        from app.config import APP_BRAND, APP_VERSION, get_db_path

        log_dir = get_db_path().parent
        log_path: Optional[Path] = log_dir / "anbardari-asan.log"
        handlers: list[logging.Handler] = [
            logging.FileHandler(log_path, encoding="utf-8"),
        ]
    except Exception:
        log_path = None
        handlers = []

    # PyInstaller --windowed / --noconsole may set sys.stderr to None.
    # Only create a console handler when a usable stderr stream exists.
    stderr = getattr(sys, "stderr", None)
    isatty = getattr(stderr, "isatty", None) if stderr is not None else None
    has_tty = bool(callable(isatty) and isatty())
    if stderr is not None and (has_tty or verbose):
        handlers.append(logging.StreamHandler(stderr))

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers or [logging.NullHandler()],
        force=True,
    )

    try:
        from app.config import APP_BRAND, APP_VERSION

        logger.info("=" * 60)
        logger.info("%s %s starting", APP_BRAND, APP_VERSION)
        if log_path is not None:
            logger.info("Log file: %s", log_path)
    except Exception:
        logger.debug("Config not importable during logging setup")
    return log_path


def _install_exception_hook() -> None:
    """نمایش و لاگ استثناهای مدیریت‌نشده."""

    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        try:
            from tkinter import messagebox

            messagebox.showerror(
                "خطای غیرمنتظره",
                f"خطای غیرمنتظره‌ای رخ داد:\n\n{exc_value}\n\n"
                "جزئیات در فایل گزارش ثبت شد.",
            )
        except Exception:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


def _fatal_error(title: str, exc: BaseException) -> None:
    """نمایش خطای مرگ‌آور به کاربر با fallback به stderr."""
    logger.critical(title, exc_info=exc)
    try:
        from tkinter import messagebox

        messagebox.showerror(title, f"{title}\n\n{exc}")
    except Exception:
        print(f"[FATAL] {title}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------- splash


def _show_splash(duration_ms: int = 1500) -> None:
    """نمایش اسپلش؛ تا بسته‌شدن آن برمی‌نگردد."""
    from app.config import APP_BRAND, APP_VERSION
    from app.ui.splash import SplashWindow

    SplashWindow(APP_BRAND, APP_VERSION, duration_ms=duration_ms).mainloop()


# ---------------------------------------------------------------- run


def _window_alive(win) -> bool:
    try:
        return bool(win.winfo_exists())
    except Exception:
        return False


def run(no_splash: bool = False, splash_ms: int = 1500) -> int:
    """راه‌اندازی برنامه. کد خروج برمی‌گرداند."""
    from app.ui.main_window import MainWindow

    if not no_splash:
        try:
            _show_splash(splash_ms)
        except Exception:
            logger.exception("Splash failed; continuing without splash")

    try:
        app = MainWindow()
    except Exception as exc:
        _fatal_error("خطا در راه‌اندازی پنجره اصلی", exc)
        return 1

    if not _window_alive(app):
        # MainWindow ممکن است خودش را به‌دلیل خطای دیتابیس destroy کرده باشد
        logger.warning("Main window closed during initialization")
        return 1

    try:
        app.mainloop()
    except Exception as exc:
        _fatal_error("خطا در اجرای برنامه", exc)
        return 1

    logger.info("Application exited cleanly")
    return 0


# ---------------------------------------------------------------- cli


def _build_parser() -> argparse.ArgumentParser:
    try:
        from app.config import APP_VERSION as version
    except Exception:
        version = "unknown"

    parser = argparse.ArgumentParser(
        prog="anbardari-asan",
        description="برنامه انبارداری آسان",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version}"
    )
    parser.add_argument(
        "--no-splash", action="store_true",
        help="پرش از صفحهٔ خوش‌آمدگویی",
    )
    parser.add_argument(
        "--splash-ms", type=int, default=1500, metavar="MS",
        help="مدت نمایش اسپلش به میلی‌ثانیه (پیش‌فرض: 1500)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="نمایش گزارش کامل در ترمینال",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    _enable_dpi_awareness()
    _setup_logging(verbose=args.verbose)
    _install_exception_hook()

    try:
        return run(no_splash=args.no_splash, splash_ms=args.splash_ms)
    except Exception as exc:
        _fatal_error("خطای غیرمنتظره در راه‌اندازی", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
