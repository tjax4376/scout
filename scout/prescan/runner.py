"""Prescan orchestration — metrics, capacity gate, confirmation.

Metadata: v0.1.1 | Scout Contributors | 2026-06-14
Change: gitignore-filtered metrics; optional file-cache RAM budget.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

import scout_core

BYTE_CAP_DEFAULT = 100 * 1024 * 1024 * 1024  # 100GB


@dataclass
class PrescanResult:
    file_count: int
    total_bytes: int
    languages: dict[str, int]
    estimated_disk_bytes: int
    estimated_ram_bytes: int
    available_disk_bytes: int
    available_ram_bytes: int


def run_prescan(
    root: Path,
    skip_globs: list[str] | None = None,
    skip_paths: list[str] | None = None,
    *,
    respect_gitignore: bool = True,
    include_file_cache: bool = False,
) -> PrescanResult:
    """Walk workspace via scout_core and compute prescan metrics."""
    if scout_core is None:
        raise RuntimeError("scout_core not built; run maturin develop")
    files = scout_core.py_scan_workspace(
        str(root),
        skip_globs=skip_globs or [],
        skip_paths=skip_paths or [],
        respect_gitignore=respect_gitignore,
    )
    total_bytes = sum(f.size for f in files)
    langs = Counter((f.language or "other") for f in files)
    # Heuristic: index.db ~2x source size; RAM ~1.5x source for graph build.
    estimated_disk = int(total_bytes * 2.2)
    estimated_ram = int(total_bytes * 1.5) + (256 * 1024 * 1024)
    if include_file_cache:
        estimated_ram += total_bytes
    usage = shutil.disk_usage(root)
    available_disk = usage.free
    available_ram = _available_ram_bytes()
    return PrescanResult(
        file_count=len(files),
        total_bytes=total_bytes,
        languages=dict(langs),
        estimated_disk_bytes=estimated_disk,
        estimated_ram_bytes=estimated_ram,
        available_disk_bytes=available_disk,
        available_ram_bytes=available_ram,
    )


def _available_ram_bytes() -> int:
    try:
        import psutil  # type: ignore

        return int(psutil.virtual_memory().available)
    except Exception:
        # Fallback when psutil not installed.
        return 8 * 1024 * 1024 * 1024


def display_prescan_table(console: Console, result: PrescanResult) -> None:
    table = Table(title="Prescan Metrics")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Files", str(result.file_count))
    table.add_row("Total size", _fmt_bytes(result.total_bytes))
    table.add_row("Est. disk", _fmt_bytes(result.estimated_disk_bytes))
    table.add_row("Est. RAM", _fmt_bytes(result.estimated_ram_bytes))
    table.add_row("Available disk", _fmt_bytes(result.available_disk_bytes))
    table.add_row("Available RAM", _fmt_bytes(result.available_ram_bytes))
    for lang, count in sorted(result.languages.items()):
        table.add_row(f"Lang: {lang}", str(count))
    console.print(table)


def check_capacity(result: PrescanResult) -> None:
    if result.available_disk_bytes < result.estimated_disk_bytes:
        raise RuntimeError("not enough capacity")
    if result.available_ram_bytes < result.estimated_ram_bytes:
        raise RuntimeError("not enough capacity")


def check_byte_cap(result: PrescanResult, byte_cap: int = BYTE_CAP_DEFAULT, force: bool = False) -> None:
    if force:
        return
    if result.total_bytes > byte_cap:
        raise RuntimeError(
            f"workspace exceeds byte cap ({_fmt_bytes(byte_cap)}); use --force to override"
        )


def write_prescan_json(path: Path, result: PrescanResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "file_count": result.file_count,
        "total_bytes": result.total_bytes,
        "languages": result.languages,
        "estimated_disk_bytes": result.estimated_disk_bytes,
        "estimated_ram_bytes": result.estimated_ram_bytes,
        "available_disk_bytes": result.available_disk_bytes,
        "available_ram_bytes": result.available_ram_bytes,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}{unit}"
        n //= 1024
    return f"{n}PB"
