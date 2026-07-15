"""Resolve TLS cert/key paths for scout serve.

Metadata: v0.1.0 | Scout Contributors | 2026-07-14
Change rationale: tls-self-signed-tailscale
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scout.config import (
    ScoutConfig,
    default_tls_cert_path,
    default_tls_key_path,
    https_required,
)


@dataclass(frozen=True)
class ResolvedTls:
    """Resolved PEM paths for uvicorn (both None = plaintext OK)."""

    certfile: Path | None
    keyfile: Path | None
    tls_enabled: bool


def _expand(path_str: str, home: Path) -> Path:
    raw = Path(path_str).expanduser()
    if raw.is_absolute():
        return raw
    return (home / raw).resolve()


def resolve_tls_for_serve(
    home: Path,
    config: ScoutConfig,
    *,
    certfile_flag: str | None = None,
    keyfile_flag: str | None = None,
) -> ResolvedTls:
    """Resolve cert/key: CLI flags → config → default ``home/tls/*.pem``.

    When HTTPS is required and files are missing, raises ``ValueError`` with
    an actionable message (caller should abort serve).
    """
    need_https = https_required(config)

    cert: Path | None = None
    key: Path | None = None

    if certfile_flag and keyfile_flag:
        cert = Path(certfile_flag).expanduser().resolve()
        key = Path(keyfile_flag).expanduser().resolve()
    elif certfile_flag or keyfile_flag:
        raise ValueError(
            "both --certfile and --keyfile are required together "
            "(or omit both to use config / ~/.scout/tls/)"
        )
    else:
        cfg_cert = (config.api.tls.certfile or "").strip()
        cfg_key = (config.api.tls.keyfile or "").strip()
        if cfg_cert and cfg_key:
            cert = _expand(cfg_cert, home)
            key = _expand(cfg_key, home)
        elif cfg_cert or cfg_key:
            raise ValueError(
                "api.tls.certfile and api.tls.keyfile must both be set (or both empty)"
            )
        else:
            default_cert = default_tls_cert_path(home)
            default_key = default_tls_key_path(home)
            if default_cert.is_file() and default_key.is_file():
                cert = default_cert
                key = default_key

    if cert is not None and key is not None:
        if not cert.is_file():
            raise ValueError(f"TLS certificate not found: {cert}")
        if not key.is_file():
            raise ValueError(f"TLS private key not found: {key}")
        return ResolvedTls(certfile=cert, keyfile=key, tls_enabled=True)

    if need_https:
        raise ValueError(
            "HTTPS is required (force_https or https:// api_base_url) but no TLS "
            "certificate/key was found.\n"
            "  Generate:  scout tls generate\n"
            "  Or pass:   scout serve --certfile PATH --keyfile PATH\n"
            "  Defaults:  ~/.scout/tls/cert.pem and key.pem"
        )

    return ResolvedTls(certfile=None, keyfile=None, tls_enabled=False)
