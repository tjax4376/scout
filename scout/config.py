"""Space config and `.scout/` storage layout.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SCOUT_DIR_NAME = ".scout"
DEFAULT_API_PORT_START = 8741


@dataclass
class EmbedConfig:
    provider: str = ""
    model: str = ""
    endpoint: str = ""
    dimensions: int = 0


@dataclass
class SpaceEntry:
    name: str
    root: str
    skip_globs: list[str] = field(default_factory=list)
    skip_paths: list[str] = field(default_factory=list)


@dataclass
class ScoutConfig:
    api_port: int = DEFAULT_API_PORT_START
    spaces: dict[str, SpaceEntry] = field(default_factory=dict)
    embed: EmbedConfig = field(default_factory=EmbedConfig)


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


def manifest_path(home: Path, space: str) -> Path:
    return space_dir(home, space) / "manifest.json"


def prescan_path(home: Path, space: str) -> Path:
    return space_dir(home, space) / "prescan.json"


def graph_bin_path(home: Path, space: str) -> Path:
    return home / "cache" / space / "graph.bin"


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
    )
    spaces: dict[str, SpaceEntry] = {}
    for name, entry in (data.get("spaces", {}) or {}).items():
        spaces[name] = SpaceEntry(
            name=name,
            root=entry.get("root", ""),
            skip_globs=list(entry.get("skip", {}).get("globs", []) or []),
            skip_paths=list(entry.get("skip", {}).get("paths", []) or []),
        )
    return ScoutConfig(
        api_port=int(data.get("api_port", DEFAULT_API_PORT_START)),
        spaces=spaces,
        embed=embed,
    )


def save_config(home: Path, config: ScoutConfig) -> None:
    payload: dict[str, Any] = {
        "api_port": config.api_port,
        "embed": {
            "provider": config.embed.provider,
            "model": config.embed.model,
            "endpoint": config.embed.endpoint,
            "dimensions": config.embed.dimensions,
        },
        "spaces": {},
    }
    for name, space in config.spaces.items():
        payload["spaces"][name] = {
            "root": space.root,
            "skip": {"globs": space.skip_globs, "paths": space.skip_paths},
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


def validate_embed(config: ScoutConfig) -> EmbedConfig:
    if not config.embed.provider:
        raise ValueError("embed provider not configured")
    if not config.embed.model:
        raise ValueError("embed model not configured")
    if config.embed.dimensions <= 0:
        raise ValueError("embed dimensions not configured")
    return config.embed


def register_space(home: Path, space: SpaceEntry, config: ScoutConfig) -> None:
    config.spaces[space.name] = space
    save_space_config(home, space)
    save_config(home, config)
    space_dir(home, space.name).mkdir(parents=True, exist_ok=True)
    graph_bin_path(home, space.name).parent.mkdir(parents=True, exist_ok=True)
