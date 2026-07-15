"""TLS helpers for scout serve (self-signed certs + path resolution).

Metadata: v0.1.0 | Scout Contributors | 2026-07-14
Change rationale: tls-self-signed-tailscale — config-driven HTTPS for Tailscale passthrough
"""

from __future__ import annotations

from scout.tls.generate import (
    OpenSslUnavailableError,
    build_san_entries,
    detect_tailscale_identity,
    generate_self_signed,
)
from scout.tls.resolve import ResolvedTls, resolve_tls_for_serve

__all__ = [
    "OpenSslUnavailableError",
    "ResolvedTls",
    "build_san_entries",
    "detect_tailscale_identity",
    "generate_self_signed",
    "resolve_tls_for_serve",
]
