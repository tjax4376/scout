"""Tests for secret log redaction."""

from __future__ import annotations

import logging

from scout.security.log_redact import SecretRedactionFilter


def test_redacts_authorization_header() -> None:
    filt = SecretRedactionFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Authorization: Bearer secret-token-value",
        args=(),
        exc_info=None,
    )
    assert filt.filter(record) is True
    assert "[REDACTED]" in record.getMessage()
    assert "secret-token-value" not in record.getMessage()
