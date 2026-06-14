"""Prescan capacity gate tests."""

from __future__ import annotations

import pytest

from scout.prescan.runner import PrescanResult, check_byte_cap, check_capacity


def test_prescan_capacity_gate_rejects() -> None:
    result = PrescanResult(
        file_count=1,
        total_bytes=10_000_000_000,
        languages={"python": 1},
        estimated_disk_bytes=20_000_000_000,
        estimated_ram_bytes=20_000_000_000,
        available_disk_bytes=1_000_000,
        available_ram_bytes=1_000_000,
    )
    with pytest.raises(RuntimeError, match="not enough capacity"):
        check_capacity(result)


def test_byte_cap_force_bypass() -> None:
    result = PrescanResult(
        file_count=1,
        total_bytes=200 * 1024**3,
        languages={"python": 1},
        estimated_disk_bytes=1000,
        estimated_ram_bytes=1000,
        available_disk_bytes=10_000_000_000,
        available_ram_bytes=10_000_000_000,
    )
    with pytest.raises(RuntimeError):
        check_byte_cap(result, force=False)
    check_byte_cap(result, force=True)
