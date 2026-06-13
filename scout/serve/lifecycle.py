"""Stop and manage scout serve process.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path

from scout.config import pid_path

TERMINATE_TIMEOUT_SECS = 5.0
KILL_TIMEOUT_SECS = 2.0
POLL_INTERVAL_SECS = 0.1


@dataclass(frozen=True)
class StopServeResult:
    """Outcome of stop_serve."""

    status: str  # stopped | not_running | stale_removed | failed
    message: str
    pid: int | None = None


def stop_serve(home: Path) -> StopServeResult:
    """Stop scout serve using PID lock at `.scout/scout.pid`."""
    pid_file = pid_path(home)
    if not pid_file.exists():
        return StopServeResult("not_running", "scout serve is not running")

    raw = pid_file.read_text(encoding="utf-8").strip()
    try:
        pid = int(raw)
    except ValueError:
        pid_file.unlink(missing_ok=True)
        return StopServeResult(
            "stale_removed",
            "removed invalid PID file; scout serve was not running",
        )

    if not _process_alive(pid):
        pid_file.unlink(missing_ok=True)
        return StopServeResult(
            "stale_removed",
            f"removed stale PID file (pid {pid}); scout serve was not running",
            pid=pid,
        )

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        return StopServeResult(
            "stale_removed",
            f"removed stale PID file (pid {pid}); scout serve was not running",
            pid=pid,
        )
    except PermissionError:
        return StopServeResult(
            "failed",
            f"permission denied stopping scout serve (pid {pid})",
            pid=pid,
        )

    if _wait_for_exit(pid, TERMINATE_TIMEOUT_SECS):
        pid_file.unlink(missing_ok=True)
        return StopServeResult(
            "stopped",
            f"stopped scout serve (pid {pid})",
            pid=pid,
        )

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        return StopServeResult(
            "stopped",
            f"stopped scout serve (pid {pid})",
            pid=pid,
        )
    except PermissionError:
        return StopServeResult(
            "failed",
            f"permission denied stopping scout serve (pid {pid})",
            pid=pid,
        )

    if _wait_for_exit(pid, KILL_TIMEOUT_SECS):
        pid_file.unlink(missing_ok=True)
        return StopServeResult(
            "stopped",
            f"stopped scout serve (pid {pid})",
            pid=pid,
        )

    return StopServeResult(
        "failed",
        f"failed to stop scout serve (pid {pid})",
        pid=pid,
    )


def _process_alive(pid: int) -> bool:
    """Return True if process is running (not dead or zombie)."""
    if pid <= 0:
        return False
    try:
        import subprocess

        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return False
        stat = proc.stdout.strip()
        if not stat:
            return False
        # Exclude zombies and fully dead states.
        return "Z" not in stat
    except (FileNotFoundError, OSError):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


def _wait_for_exit(pid: int, timeout: float) -> bool:
    """Poll until process exits or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            return True
        time.sleep(POLL_INTERVAL_SECS)
    return not _process_alive(pid)
