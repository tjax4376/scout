"""Redact secrets from log records.

Metadata: v1.0.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import logging
import re
from typing import ClassVar

_REDACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(Authorization\s*[:=]\s*)(Bearer\s+)?\S+", re.IGNORECASE),
    re.compile(r"([\"']?(?:api_key|token|secret)[\"']?\s*[:=]\s*)([\"']?)[^\"'\s,}]+", re.IGNORECASE),
    re.compile(r"\b(openrouter|lmstudio|omlx|unsloth_studio)_api_key\s*[:=]\s*\S+", re.IGNORECASE),
)

_INSTALLED = False


class SecretRedactionFilter(logging.Filter):
    """Strip API keys and bearer tokens from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = message
        for pattern in _REDACT_PATTERNS:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def install_secret_redaction() -> None:
    """Attach redaction filter to root logger once per process."""
    global _INSTALLED
    if _INSTALLED:
        return
    filt = SecretRedactionFilter()
    logging.getLogger().addFilter(filt)
    for name in ("scout", "uvicorn", "uvicorn.access"):
        logging.getLogger(name).addFilter(filt)
    _INSTALLED = True
