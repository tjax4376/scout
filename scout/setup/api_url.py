"""Scout API base URL helpers.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
Updated: 2026-06-14 — detect running scout serve on occupied ports.
"""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from scout.config import (
    DEFAULT_API_PORT_START,
    ScoutConfig,
    default_api_base_url,
    is_loopback_host,
)

DEFAULT_API_BASE_URL = f"http://127.0.0.1:{DEFAULT_API_PORT_START}/v1"
API_PORT_RANGE_END = 8799


@dataclass(frozen=True)
class ApiEndpoint:
    scheme: str
    host: str
    port: int


def normalize_api_base_url(raw: str) -> str:
    """Validate and normalize Scout API base URL to scheme://host:port/v1."""
    text = raw.strip().rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("API URL must use http or https scheme")
    if not parsed.hostname:
        raise ValueError("API URL must include host")
    if parsed.port is None:
        raise ValueError("API URL must include explicit port")
    path = parsed.path.rstrip("/") or ""
    if path != "/v1":
        raise ValueError("API URL path must be /v1")
    scheme = parsed.scheme
    if scheme == "http" and not is_loopback_host(parsed.hostname):
        scheme = "https"
    return f"{scheme}://{parsed.hostname}:{parsed.port}/v1"


def parse_api_base_url(url: str) -> ApiEndpoint:
    """Parse normalized api_base_url into bind endpoint."""
    normalized = normalize_api_base_url(url)
    parsed = urlparse(normalized)
    assert parsed.hostname is not None
    assert parsed.port is not None
    return ApiEndpoint(
        scheme=parsed.scheme,
        host=parsed.hostname,
        port=parsed.port,
    )


def build_scout_api_url(config: ScoutConfig) -> str:
    """Return canonical Scout API base URL from config."""
    if config.api_base_url:
        return normalize_api_base_url(config.api_base_url)
    return default_api_base_url(config.api_port)


def migrate_api_base_url(config: ScoutConfig) -> None:
    """Ensure api_base_url is set; derive from api_port if missing."""
    if not config.api_base_url:
        config.api_base_url = default_api_base_url(config.api_port)


def update_api_base_url_port(config: ScoutConfig, port: int) -> None:
    """Update api_base_url and api_port after port reassignment."""
    endpoint = parse_api_base_url(build_scout_api_url(config))
    config.api_port = port
    config.api_base_url = f"{endpoint.scheme}://{endpoint.host}:{port}/v1"


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def find_free_api_port_on_host(
    host: str,
    start: int = DEFAULT_API_PORT_START,
    end: int = API_PORT_RANGE_END,
) -> int:
    """Find first free port on host in range."""
    for port in range(start, end + 1):
        if not _port_open(host, port):
            return port
    raise RuntimeError(f"no free API port found on {host} in range {start}-{end}")


def probe_scout_health(base_url: str, *, timeout: float = 0.5) -> bool:
    """Return True when URL responds like Scout GET /v1/health."""
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(f"{url}/health")
            if resp.status_code != 200:
                return False
            data = resp.json()
            return isinstance(data, dict) and data.get("status") == "ok"
    except (httpx.HTTPError, ValueError, TypeError):
        return False


def discover_scout_api_url(
    host: str = "127.0.0.1",
    start: int = DEFAULT_API_PORT_START,
    end: int = API_PORT_RANGE_END,
) -> str | None:
    """Scan local ports for a running Scout API."""
    for port in range(start, end + 1):
        if not _port_open(host, port):
            continue
        candidate = f"http://{host}:{port}/v1"
        if probe_scout_health(candidate):
            return candidate
    return None


def resolve_discovered_api_url(config: ScoutConfig) -> str | None:
    """Prefer configured URL when healthy, else scan default port range."""
    if config.api_base_url:
        try:
            normalized = normalize_api_base_url(config.api_base_url)
        except ValueError:
            normalized = ""
        if normalized and probe_scout_health(normalized):
            return normalized
    elif config.api_port:
        candidate = f"http://127.0.0.1:{config.api_port}/v1"
        if probe_scout_health(candidate):
            return candidate
    return discover_scout_api_url()


def ensure_api_port_available(config: ScoutConfig) -> None:
    """Keep URL when scout serves there; otherwise pick a free port if occupied."""
    endpoint = parse_api_base_url(build_scout_api_url(config))
    if not _port_open(endpoint.host, endpoint.port):
        return
    current = f"{endpoint.scheme}://{endpoint.host}:{endpoint.port}/v1"
    if probe_scout_health(current):
        return
    new_port = find_free_api_port_on_host(
        endpoint.host,
        start=endpoint.port,
        end=API_PORT_RANGE_END,
    )
    update_api_base_url_port(config, new_port)


_GIT_URL_RE = re.compile(r"^(https?|git|ssh)://", re.IGNORECASE)
_SSH_GIT_RE = re.compile(r"^git@[\w.-]+:")


def validate_git_url(url: str) -> str:
    """Validate git remote URL scheme."""
    text = url.strip()
    if _GIT_URL_RE.match(text) or _SSH_GIT_RE.match(text):
        return text
    raise ValueError("git URL must use https, git, ssh, or git@host:path form")


def validate_subdir_name(name: str) -> str:
    """Reject unsafe subdirectory names."""
    text = name.strip()
    if not text or text in {".", ".."}:
        raise ValueError("invalid subdirectory name")
    if "/" in text or "\\" in text or ".." in text:
        raise ValueError("subdirectory name must be a single path segment")
    if re.search(r"[`$;|&<>]", text):
        raise ValueError("subdirectory name contains unsafe characters")
    return text


def repo_name_from_url(url: str) -> str:
    """Derive default clone directory name from git URL."""
    text = url.strip().rstrip("/")
    if ":" in text and "@" in text.split(":")[0]:
        # git@host:org/repo.git
        tail = text.split(":", 1)[-1]
    else:
        tail = urlparse(text).path or text.split("/")[-1]
    name = tail.rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name or "repo"
