"""Generate self-signed TLS certificates via openssl.

Metadata: v0.1.0 | Scout Contributors | 2026-07-14
Change rationale: tls-self-signed-tailscale
"""

from __future__ import annotations

import ipaddress
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from scout.config import (
    ScoutConfig,
    default_tls_cert_path,
    default_tls_key_path,
    tls_dir,
)

_LOG = logging.getLogger("scout.tls.generate")


class OpenSslUnavailableError(RuntimeError):
    """Raised when the openssl CLI is not on PATH."""


@dataclass(frozen=True)
class TailscaleIdentity:
    ipv4: str | None = None
    dns_name: str | None = None


def detect_tailscale_identity() -> TailscaleIdentity:
    """Best-effort Tailscale IPv4 + MagicDNS from ``tailscale status --json``."""
    if shutil.which("tailscale") is None:
        return TailscaleIdentity()
    try:
        proc = subprocess.run(
            ["tailscale", "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _LOG.debug("tailscale status failed: %s", exc)
        return TailscaleIdentity()
    if proc.returncode != 0 or not proc.stdout.strip():
        return TailscaleIdentity()
    try:
        import json

        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return TailscaleIdentity()

    ipv4: str | None = None
    dns_name: str | None = None
    self_node = data.get("Self") or {}
    for addr in self_node.get("TailscaleIPs") or []:
        try:
            parsed = ipaddress.ip_address(str(addr))
        except ValueError:
            continue
        if isinstance(parsed, ipaddress.IPv4Address):
            ipv4 = str(parsed)
            break
    dns_name = self_node.get("DNSName") or None
    if isinstance(dns_name, str):
        dns_name = dns_name.rstrip(".")
        if not dns_name:
            dns_name = None
    return TailscaleIdentity(ipv4=ipv4, dns_name=dns_name)


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def build_san_entries(
    api_base_url: str,
    *,
    tailscale: TailscaleIdentity | None = None,
    extra_dns: list[str] | None = None,
    extra_ips: list[str] | None = None,
) -> list[str]:
    """Build openssl ``subjectAltName`` value pieces (DNS:… / IP:…)."""
    dns: set[str] = {"localhost"}
    ips: set[str] = {"127.0.0.1", "::1"}

    host = urlparse(api_base_url).hostname
    if host:
        if _is_ip(host):
            ips.add(host)
        else:
            dns.add(host.lower())

    ts = tailscale if tailscale is not None else TailscaleIdentity()
    if ts.ipv4:
        ips.add(ts.ipv4)
    if ts.dns_name:
        dns.add(ts.dns_name.lower())

    for name in extra_dns or []:
        if name:
            dns.add(name.lower())
    for addr in extra_ips or []:
        if addr:
            ips.add(addr)

    entries: list[str] = []
    for name in sorted(dns):
        entries.append(f"DNS:{name}")
    for addr in sorted(ips, key=str):
        entries.append(f"IP:{addr}")
    return entries


def _cn_from_url(api_base_url: str) -> str:
    host = urlparse(api_base_url).hostname
    return host or "localhost"


def generate_self_signed(
    home: Path,
    config: ScoutConfig,
    *,
    days: int = 825,
    openssl_bin: str | None = None,
) -> tuple[Path, Path]:
    """Generate self-signed cert+key under ``home/tls/``; return (cert, key).

    Raises ``OpenSslUnavailableError`` if openssl is missing.
    """
    openssl = openssl_bin or shutil.which("openssl")
    if not openssl:
        raise OpenSslUnavailableError(
            "openssl not found on PATH — install OpenSSL to generate Scout TLS certs"
        )

    out_dir = tls_dir(home)
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)

    cert_path = default_tls_cert_path(home)
    key_path = default_tls_key_path(home)
    ts = detect_tailscale_identity()
    sans = build_san_entries(config.api_base_url, tailscale=ts)
    cn = _cn_from_url(config.api_base_url)
    san_line = ",".join(sans)

    with tempfile.TemporaryDirectory(prefix="scout-tls-") as tmp:
        tmp_path = Path(tmp)
        conf_path = tmp_path / "openssl.cnf"
        conf_path.write_text(
            "\n".join(
                [
                    "[req]",
                    "default_bits = 4096",
                    "prompt = no",
                    "default_md = sha256",
                    "distinguished_name = dn",
                    "x509_extensions = v3_req",
                    "",
                    "[dn]",
                    f"CN = {cn}",
                    "O = Scout",
                    "OU = Self-Signed",
                    "",
                    "[v3_req]",
                    "basicConstraints = CA:FALSE",
                    "keyUsage = digitalSignature, keyEncipherment",
                    "extendedKeyUsage = serverAuth",
                    f"subjectAltName = {san_line}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        cmd = [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:4096",
            "-sha256",
            "-days",
            str(days),
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-config",
            str(conf_path),
        ]
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"openssl failed (exit {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
            )

    os.chmod(key_path, 0o600)
    os.chmod(cert_path, 0o644)
    _LOG.info("wrote TLS cert %s key %s (SAN: %s)", cert_path, key_path, san_line)
    return cert_path, key_path
