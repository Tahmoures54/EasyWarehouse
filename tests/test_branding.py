"""Regression tests for the user-facing application identity."""

from app.config import APP_BRAND, APP_TITLE


def test_persian_application_branding() -> None:
    assert APP_BRAND == "انبارداری آسان"
    assert APP_BRAND in APP_TITLE
