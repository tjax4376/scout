"""Space config and `.scout/` storage layout.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

_LOG = logging.getLogger("scout.config")

_LOCALHOST_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def is_loopback_host(hostname: str | None) -> bool:
    """Return True when hostname is a local-only bind address."""
    return (hostname or "127.0.0.1").lower() in _LOCALHOST_HOSTS


def default_api_scheme(host: str) -> str:
    """Loopback uses HTTP for local dev; other hosts default to HTTPS."""
    return "http" if is_loopback_host(host) else "https"


def default_api_base_url(port: int, host: str = "127.0.0.1") -> str:
    """Build default api_base_url from port and bind host."""
    scheme = default_api_scheme(host)
    return f"{scheme}://{host}:{port}/v1"

SCOUT_DIR_NAME = ".scout"
DEFAULT_API_PORT_START = 8741


@dataclass
class EmbedConfig:
    provider: str = ""
    model: str = ""
    endpoint: str = ""
    dimensions: int = 0
    embed_batch_size: int = 10  # 0 = auto-probe; default 10 for session embed
    compress_chunks: bool = True
    compress_strip_line_comments: bool = False


@dataclass
class SpaceEntry:
    name: str
    root: str
    skip_globs: list[str] = field(default_factory=list)
    skip_paths: list[str] = field(default_factory=list)
    respect_gitignore: bool = True


def space_scan_kwargs(entry: SpaceEntry) -> dict[str, object]:
    """Keyword args for scout_core.py_scan_workspace from a space entry."""
    return {
        "skip_globs": entry.skip_globs,
        "skip_paths": entry.skip_paths,
        "respect_gitignore": entry.respect_gitignore,
    }


@dataclass
class AuthConfig:
    enabled: bool = False
    key: str = ""
    admin_key: str = ""
    health_public: bool = True


@dataclass
class RateLimitConfig:
    search_per_minute: int = 60
    reindex_per_hour: int = 3


@dataclass
class ApiConfig:
    auth: AuthConfig = field(default_factory=AuthConfig)
    cors_origins: list[str] = field(
        default_factory=lambda: [
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ]
    )
    force_https: bool = False
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)


@dataclass
class ScoutConfig:
    api_port: int = DEFAULT_API_PORT_START
    api_base_url: str = ""
    spaces: dict[str, SpaceEntry] = field(default_factory=dict)
    embed: EmbedConfig = field(default_factory=EmbedConfig)
    api: ApiConfig = field(default_factory=ApiConfig)


def scout_home(cwd: Path | None = None) -> Path:
    """Resolve `.scout/` directory (cwd-first, then home)."""
    base = cwd or Path.cwd()
    local = base / SCOUT_DIR_NAME
    if local.exists():
        return local
    return Path.home() / SCOUT_DIR_NAME


def bootstrap_scout_dir(home: Path | None = None) -> Path:
    """Create `.scout/` with config templates if missing."""
    root = home or scout_home()
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "config.yaml"
    if not config_path.exists():
        default = ScoutConfig()
        save_config(root, default)
    secrets_path = root / "secrets.yaml"
    if not secrets_path.exists():
        secrets_path.write_text("# Scout secrets — API keys only\n", encoding="utf-8")
        os.chmod(secrets_path, 0o600)
    (root / "cache").mkdir(exist_ok=True)
    (root / "spaces").mkdir(exist_ok=True)
    return root


def config_path(home: Path) -> Path:
    return home / "config.yaml"


def secrets_path(home: Path) -> Path:
    return home / "secrets.yaml"


def pid_path(home: Path) -> Path:
    return home / "scout.pid"


def space_dir(home: Path, space: str) -> Path:
    return home / "spaces" / space


def space_config_path(home: Path, space: str) -> Path:
    return space_dir(home, space) / "config.yaml"


def index_db_path(home: Path, space: str) -> Path:
    return space_dir(home, space) / "index.db"


def session_index_path(home: Path, space: str) -> Path:
    """Per-space session vector index (cleared on `scout serve --embed` start)."""
    return space_dir(home, space) / "session_index.db"


def manifest_path(home: Path, space: str) -> Path:
    return space_dir(home, space) / "manifest.json"


def prescan_path(home: Path, space: str) -> Path:
    return space_dir(home, space) / "prescan.json"


def graph_bin_path(home: Path, space: str) -> Path:
    return home / "cache" / space / "graph.bin"


def _parse_auth_config(raw: dict[str, Any]) -> AuthConfig:
    return AuthConfig(
        enabled=bool(raw.get("enabled", False)),
        key=str(raw.get("key", "") or ""),
        admin_key=str(raw.get("admin_key", "") or ""),
        health_public=bool(raw.get("health_public", True)),
    )


def _parse_api_config(data: dict[str, Any]) -> ApiConfig:
    api_raw = data.get("api", {}) or {}
    auth_raw = api_raw.get("auth", {}) or {}
    rate_raw = api_raw.get("rate_limit", {}) or {}
    cors = api_raw.get("cors_origins")
    origins = list(cors) if isinstance(cors, list) else None
    return ApiConfig(
        auth=_parse_auth_config(auth_raw),
        cors_origins=origins
        if origins is not None
        else ApiConfig().cors_origins,
        force_https=bool(api_raw.get("force_https", False)),
        rate_limit=RateLimitConfig(
            search_per_minute=int(rate_raw.get("search_per_minute", 60) or 60),
            reindex_per_hour=int(rate_raw.get("reindex_per_hour", 3) or 3),
        ),
    )


def _apply_api_env_overrides(api: ApiConfig) -> ApiConfig:
    if os.environ.get("SCOUT_API_KEY"):
        api.auth.key = os.environ["SCOUT_API_KEY"]
    if os.environ.get("SCOUT_ADMIN_KEY"):
        api.auth.admin_key = os.environ["SCOUT_ADMIN_KEY"]
    if os.environ.get("SCOUT_FORCE_HTTPS", "").lower() in {"1", "true", "yes"}:
        api.force_https = True
    cors_env = os.environ.get("SCOUT_CORS_ORIGINS", "").strip()
    if cors_env:
        api.cors_origins = [part.strip() for part in cors_env.split(",") if part.strip()]
    if os.environ.get("SCOUT_AUTH_ENABLED", "").lower() in {"1", "true", "yes"}:
        api.auth.enabled = True
    if os.environ.get("SCOUT_AUTH_ENABLED", "").lower() in {"0", "false", "no"}:
        api.auth.enabled = False
    return api


def _default_auth_for_bind(api_base_url: str, auth: AuthConfig) -> AuthConfig:
    """Enable auth by default when binding beyond loopback unless explicitly configured."""
    if auth.enabled or auth.key or auth.admin_key:
        return auth
    parsed = urlparse(api_base_url)
    if not is_loopback_host(parsed.hostname):
        auth.enabled = True
    return auth


def _upgrade_api_base_url_scheme(api_base_url: str) -> str:
    """Use HTTPS scheme for non-loopback hosts (cleartext LAN binds are upgraded)."""
    parsed = urlparse(api_base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    if port is None:
        return api_base_url
    if parsed.scheme == "http" and not is_loopback_host(host):
        return f"https://{host}:{port}/v1"
    return api_base_url


def _apply_force_https_policy(api: ApiConfig, api_base_url: str) -> None:
    """Enable HTTPS redirect when URL or bind host requires transport security."""
    parsed = urlparse(api_base_url)
    if parsed.scheme == "https" or not is_loopback_host(parsed.hostname):
        api.force_https = True


def warn_insecure_secrets_file(home: Path) -> None:
    """Warn when secrets.yaml is world-readable on Unix."""
    path = secrets_path(home)
    if not path.exists():
        return
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        _LOG.warning("secrets.yaml is world-readable; run chmod 600 %s", path)


def load_config(home: Path) -> ScoutConfig:
    path = config_path(home)
    if not path.exists():
        return ScoutConfig()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    embed_raw = data.get("embed", {}) or {}
    embed = EmbedConfig(
        provider=embed_raw.get("provider", ""),
        model=embed_raw.get("model", ""),
        endpoint=embed_raw.get("endpoint", ""),
        dimensions=int(embed_raw.get("dimensions", 0) or 0),
        embed_batch_size=int(
            embed_raw["embed_batch_size"]
            if "embed_batch_size" in embed_raw
            else 10
        ),
        compress_chunks=bool(embed_raw.get("compress_chunks", True)),
        compress_strip_line_comments=bool(
            embed_raw.get("compress_strip_line_comments", False)
        ),
    )
    spaces: dict[str, SpaceEntry] = {}
    for name, entry in (data.get("spaces", {}) or {}).items():
        spaces[name] = SpaceEntry(
            name=name,
            root=entry.get("root", ""),
            skip_globs=list(entry.get("skip", {}).get("globs", []) or []),
            skip_paths=list(entry.get("skip", {}).get("paths", []) or []),
            respect_gitignore=bool(entry.get("respect_gitignore", True)),
        )
    api_port = int(data.get("api_port", DEFAULT_API_PORT_START))
    api_base_url = str(data.get("api_base_url", "") or "")
    if not api_base_url:
        api_base_url = default_api_base_url(api_port)
    else:
        api_base_url = _upgrade_api_base_url_scheme(api_base_url)
    api = _apply_api_env_overrides(_parse_api_config(data))
    _apply_force_https_policy(api, api_base_url)
    api.auth = _default_auth_for_bind(api_base_url, api.auth)
    return ScoutConfig(
        api_port=api_port,
        api_base_url=api_base_url,
        spaces=spaces,
        embed=embed,
        api=api,
    )


def save_config(home: Path, config: ScoutConfig) -> None:
    payload: dict[str, Any] = {
        "api_port": config.api_port,
        "api_base_url": config.api_base_url,
        "embed": {
            "provider": config.embed.provider,
            "model": config.embed.model,
            "endpoint": config.embed.endpoint,
            "dimensions": config.embed.dimensions,
            "embed_batch_size": config.embed.embed_batch_size,
            "compress_chunks": config.embed.compress_chunks,
            "compress_strip_line_comments": config.embed.compress_strip_line_comments,
        },
        "spaces": {},
    }
    for name, space in config.spaces.items():
        payload["spaces"][name] = {
            "root": space.root,
            "skip": {"globs": space.skip_globs, "paths": space.skip_paths},
            "respect_gitignore": space.respect_gitignore,
        }
    payload["api"] = {
        "auth": {
            "enabled": config.api.auth.enabled,
            "key": config.api.auth.key,
            "admin_key": config.api.auth.admin_key,
            "health_public": config.api.auth.health_public,
        },
        "cors_origins": list(config.api.cors_origins),
        "force_https": config.api.force_https,
        "rate_limit": {
            "search_per_minute": config.api.rate_limit.search_per_minute,
            "reindex_per_hour": config.api.rate_limit.reindex_per_hour,
        },
    }
    config_path(home).write_text(
        yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
    )


def embed_api_key_secret(provider: str) -> str:
    """secrets.yaml key for a provider's embed API key."""
    return f"{provider.replace('-', '_')}_api_key"


def get_embed_api_key(secrets: dict[str, str], provider: str) -> str | None:
    key = secrets.get(embed_api_key_secret(provider))
    return key if key else None


def load_secrets(home: Path) -> dict[str, str]:
    secrets: dict[str, str] = {}
    path = secrets_path(home)
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        secrets = {str(k): str(v) for k, v in data.items()}

    if os.environ.get("OPENROUTER_API_KEY"):
        secrets["openrouter_api_key"] = os.environ["OPENROUTER_API_KEY"]
    for provider in ("lmstudio", "omlx", "unsloth-studio"):
        env_name = f"{provider.upper().replace('-', '_')}_API_KEY"
        if os.environ.get(env_name):
            secrets[embed_api_key_secret(provider)] = os.environ[env_name]
    return secrets


def save_secrets(home: Path, secrets: dict[str, str]) -> None:
    path = secrets_path(home)
    path.write_text(yaml.safe_dump(secrets, sort_keys=False), encoding="utf-8")
    os.chmod(path, 0o600)


def load_space_config(home: Path, space: str) -> SpaceEntry:
    path = space_config_path(home, space)
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return SpaceEntry(
            name=space,
            root=data.get("root", ""),
            skip_globs=list(data.get("skip", {}).get("globs", []) or []),
            skip_paths=list(data.get("skip", {}).get("paths", []) or []),
            respect_gitignore=bool(data.get("respect_gitignore", True)),
        )
    cfg = load_config(home)
    if space in cfg.spaces:
        return cfg.spaces[space]
    raise ValueError(f"unknown space: {space}")


def save_space_config(home: Path, space: SpaceEntry) -> None:
    dest = space_config_path(home, space.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "root": space.root,
        "skip": {"globs": space.skip_globs, "paths": space.skip_paths},
        "respect_gitignore": space.respect_gitignore,
    }
    dest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def validate_space(home: Path, space: str) -> SpaceEntry:
    """Validate space exists and root path is valid."""
    entry = load_space_config(home, space)
    if not entry.root:
        raise ValueError(f"space {space} has no root path configured")
    root = Path(entry.root).expanduser()
    if not root.is_dir():
        raise ValueError(f"space root not found: {root}")
    entry.root = str(root.resolve())
    return entry


def _validate_embed_endpoint(endpoint: str) -> None:
    if not endpoint:
        return
    parsed = urlparse(endpoint.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"invalid embed endpoint URL: {endpoint!r}")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" and host not in _LOCALHOST_HOSTS:
        raise ValueError(
            f"embed endpoint must use https:// for non-localhost hosts: {endpoint!r}"
        )


def validate_embed(config: ScoutConfig) -> EmbedConfig:
    if not config.embed.provider:
        raise ValueError("embed provider not configured")
    if not config.embed.model:
        raise ValueError("embed model not configured")
    if config.embed.dimensions <= 0:
        raise ValueError("embed dimensions not configured")
    _validate_embed_endpoint(config.embed.endpoint)
    return config.embed


def register_space(home: Path, space: SpaceEntry, config: ScoutConfig) -> None:
    config.spaces[space.name] = space
    save_space_config(home, space)
    save_config(home, config)
    space_dir(home, space.name).mkdir(parents=True, exist_ok=True)
    graph_bin_path(home, space.name).parent.mkdir(parents=True, exist_ok=True)
