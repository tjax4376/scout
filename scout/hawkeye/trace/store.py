"""Append-only JSONL trace store for Hawkeye review sessions.

Metadata: v1.1.0 | Scout Contributors | 2026-06-15
Change rationale: File locking, record validation, load_or_empty helper.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@contextlib.contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    """Exclusive lock for append on Unix; best-effort no-op elsewhere."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _validate_record(record: dict[str, Any]) -> bool:
    if not record.get("type"):
        return False
    if record.get("type") == "step" and not record.get("action"):
        return False
    return True


def _parse_record_line(line: str, *, warn: bool = True) -> dict[str, Any] | None:
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        if warn:
            print(f"hawkeye trace: skipping malformed JSON line", file=sys.stderr)
        return None
    if not isinstance(record, dict):
        if warn:
            print("hawkeye trace: skipping non-object record", file=sys.stderr)
        return None
    if not _validate_record(record):
        if warn:
            print("hawkeye trace: skipping record missing required fields", file=sys.stderr)
        return None
    return record


class TraceStore:
    """One JSONL file per review session."""

    def __init__(self, trace_dir: Path, session_id: str) -> None:
        self.trace_dir = trace_dir
        self.session_id = session_id
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.path = trace_dir / f"{session_id}.jsonl"
        self._seq = 0
        self._findings: list[dict[str, Any]] = []
        self._feedback: dict[str, str] = {}

    def append(self, record: dict[str, Any]) -> None:
        record = dict(record)
        record.setdefault("session_id", self.session_id)
        record.setdefault("timestamp", _now_iso())
        line = json.dumps(record, sort_keys=True) + "\n"
        with _file_lock(self.path):
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def start_session(
        self,
        *,
        space: str,
        diff_ref: str,
        changed_paths: list[str],
        **metadata: Any,
    ) -> None:
        record: dict[str, Any] = {
            "type": "session_start",
            "space": space,
            "diff_ref": diff_ref,
            "changed_paths": changed_paths,
        }
        record.update(metadata)
        self.append(record)

    def log_step(self, action: str, **fields: Any) -> int:
        self._seq += 1
        self.append({"type": "step", "seq": self._seq, "action": action, **fields})
        return self._seq

    def add_finding(self, finding: dict[str, Any]) -> None:
        self._findings.append(finding)
        self.append({"type": "finding", "finding": finding})

    def end_session(self, findings_hash: str) -> None:
        self.append(
            {
                "type": "session_end",
                "findings_count": len(self._findings),
                "findings_hash": findings_hash,
            }
        )

    def record_feedback(self, finding_id: str, verdict: str) -> None:
        self._feedback[finding_id] = verdict
        self.append(
            {
                "type": "feedback",
                "finding_id": finding_id,
                "verdict": verdict,
            }
        )

    @property
    def findings(self) -> list[dict[str, Any]]:
        return list(self._findings)

    @classmethod
    def load(cls, trace_dir: Path, session_id: str) -> TraceStore:
        store = cls(trace_dir, session_id)
        if not store.path.exists():
            raise FileNotFoundError(f"trace not found: {store.path}")
        store._hydrate_from_path(warn=True)
        return store

    @classmethod
    def load_or_empty(cls, trace_dir: Path, session_id: str) -> TraceStore:
        store = cls(trace_dir, session_id)
        if store.path.exists():
            store._hydrate_from_path(warn=True)
        return store

    def _hydrate_from_path(self, *, warn: bool) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = _parse_record_line(line, warn=warn)
            if record is None:
                continue
            if record.get("type") == "step":
                self._seq = max(self._seq, int(record.get("seq") or 0))
            elif record.get("type") == "finding":
                self._findings.append(record.get("finding") or {})
            elif record.get("type") == "feedback":
                fid = str(record.get("finding_id") or "")
                if fid:
                    self._feedback[fid] = str(record.get("verdict") or "")

    def iter_records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = _parse_record_line(line, warn=True)
            if record is not None:
                out.append(record)
        return out

    def steps(self) -> list[dict[str, Any]]:
        return [r for r in self.iter_records() if r.get("type") == "step"]
