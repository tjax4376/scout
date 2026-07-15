"""Tests for Scout TLS path resolution and SAN generation.

Metadata: v0.1.0 | Scout Contributors | 2026-07-14
Change rationale: tls-self-signed-tailscale
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scout.config import (
    ApiConfig,
    ScoutConfig,
    TlsConfig,
    bootstrap_scout_dir,
    load_config,
    save_config,
)
from scout.tls.generate import (
    OpenSslUnavailableError,
    TailscaleIdentity,
    build_san_entries,
    generate_self_signed,
)
from scout.tls.resolve import resolve_tls_for_serve


def test_build_san_includes_api_host_and_localhost() -> None:
    sans = build_san_entries(
        "https://100.95.179.57:8741/v1",
        tailscale=TailscaleIdentity(),
    )
    assert "DNS:localhost" in sans
    assert "IP:127.0.0.1" in sans
    assert "IP:100.95.179.57" in sans


def test_build_san_includes_tailscale_identity() -> None:
    sans = build_san_entries(
        "https://100.95.179.57:8741/v1",
        tailscale=TailscaleIdentity(
            ipv4="100.95.179.57",
            dns_name="evo-tjax.taild02f0a.ts.net",
        ),
    )
    assert "DNS:evo-tjax.taild02f0a.ts.net" in sans
    assert "IP:100.95.179.57" in sans


def test_tls_config_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scout.config.scout_home", lambda cwd=None: tmp_path / ".scout")
    home = bootstrap_scout_dir()
    cfg = ScoutConfig(
        api_port=8741,
        api_base_url="https://100.95.179.57:8741/v1",
        api=ApiConfig(
            force_https=True,
            tls=TlsConfig(certfile="/tmp/c.pem", keyfile="/tmp/k.pem"),
        ),
    )
    save_config(home, cfg)
    loaded = load_config(home)
    assert loaded.api.tls.certfile == "/tmp/c.pem"
    assert loaded.api.tls.keyfile == "/tmp/k.pem"
    assert loaded.api.force_https is True


def test_resolve_tls_flags_override(tmp_path: Path) -> None:
    home = tmp_path / ".scout"
    home.mkdir()
    cert = tmp_path / "flag-cert.pem"
    key = tmp_path / "flag-key.pem"
    cert.write_text("cert")
    key.write_text("key")
    cfg = ScoutConfig(
        api_base_url="https://10.0.0.1:8741/v1",
        api=ApiConfig(
            force_https=True,
            tls=TlsConfig(certfile="/nope.pem", keyfile="/nope.key"),
        ),
    )
    resolved = resolve_tls_for_serve(
        home, cfg, certfile_flag=str(cert), keyfile_flag=str(key)
    )
    assert resolved.tls_enabled is True
    assert resolved.certfile == cert.resolve()
    assert resolved.keyfile == key.resolve()


def test_resolve_tls_https_required_missing_raises(tmp_path: Path) -> None:
    home = tmp_path / ".scout"
    home.mkdir()
    cfg = ScoutConfig(
        api_base_url="https://100.95.179.57:8741/v1",
        api=ApiConfig(force_https=True),
    )
    with pytest.raises(ValueError, match="scout tls generate"):
        resolve_tls_for_serve(home, cfg)


def test_resolve_tls_loopback_plaintext_ok(tmp_path: Path) -> None:
    home = tmp_path / ".scout"
    home.mkdir()
    cfg = ScoutConfig(api_base_url="http://127.0.0.1:8741/v1")
    resolved = resolve_tls_for_serve(home, cfg)
    assert resolved.tls_enabled is False
    assert resolved.certfile is None


def test_generate_missing_openssl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scout.tls.generate.shutil.which", lambda _name: None)
    home = tmp_path / ".scout"
    home.mkdir()
    cfg = ScoutConfig(api_base_url="https://100.95.179.57:8741/v1")
    with pytest.raises(OpenSslUnavailableError, match="openssl not found"):
        generate_self_signed(home, cfg)


@pytest.mark.skipif(
    __import__("shutil").which("openssl") is None,
    reason="openssl not installed",
)
def test_generate_self_signed_writes_files(tmp_path: Path) -> None:
    home = tmp_path / ".scout"
    home.mkdir()
    cfg = ScoutConfig(api_base_url="https://100.95.179.57:8741/v1")
    cert, key = generate_self_signed(home, cfg)
    assert cert.is_file()
    assert key.is_file()
    assert (key.stat().st_mode & 0o777) == 0o600
    assert (cert.parent.stat().st_mode & 0o777) == 0o700
