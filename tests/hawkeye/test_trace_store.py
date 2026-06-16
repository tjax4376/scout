"""Trace store safety tests."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from scout.hawkeye.trace.store import TraceStore


def test_load_or_empty_missing(tmp_path: Path) -> None:
    store = TraceStore.load_or_empty(tmp_path / "traces", "missing")
    assert store.path.exists() is False
    assert store.iter_records() == []


def test_load_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="trace not found"):
        TraceStore.load(tmp_path / "traces", "nope")


def test_iter_records_skips_malformed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    traces = tmp_path / "traces"
    traces.mkdir()
    path = traces / "sess.jsonl"
    good = {
        "type": "step",
        "action": "symbols",
        "session_id": "sess",
        "timestamp": "2026-06-15T00:00:00+00:00",
        "seq": 1,
    }
    path.write_text("not json\n" + json.dumps(good) + "\n")
    store = TraceStore.load(traces, "sess")
    records = store.iter_records()
    assert len(records) == 1
    assert "malformed" in capsys.readouterr().err.lower()


def test_concurrent_append(tmp_path: Path) -> None:
    traces = tmp_path / "traces"
    store = TraceStore(traces, "concurrent")

    def worker(n: int) -> None:
        for i in range(5):
            store.append({"type": "step", "action": "symbols", "seq": n * 10 + i})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = [ln for ln in store.path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 20
    for line in lines:
        json.loads(line)
