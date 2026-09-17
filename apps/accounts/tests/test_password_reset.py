"""Unit tests for password-reset helpers."""
from __future__ import annotations

import pytest

from apps.accounts.services.password_reset_service import normalize_otp_input


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("123456", "123456"),
        ("12 34 56", "123456"),
        ("12-34-56", "123456"),
        ("abc", ""),
        ("", ""),
    ],
)
def test_normalize_otp_input(raw, expected):
    assert normalize_otp_input(raw) == expected
