"""Session embed API tests (`scout serve --embed`)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from scout.api.app import create_app
from scout.config import EmbedConfig, ScoutConfig, SpaceEntry, save_config
from tests.conftest import requires_scout_core


@pytest.fixture
def embed_config(scout_home: Path, sample_project: Path) -> ScoutConfig:
    space = "demo"
    return ScoutConfig(
        spaces={space: SpaceEntry(name=space, root=str(sample_project))},
        embed=EmbedConfig(
            provider="lmstudio",
            model="test-model",
            dimensions=4,
            endpoint="http://127.0.0.1:1234",
        ),
    )


@pytest.fixture
def embed_indexed_space(
    graph_indexed_space: tuple[str, Path],
    embed_config: ScoutConfig,
    scout_home: Path,
) -> tuple[str, Path]:
    space, _ = graph_indexed_space
    save_config(scout_home, embed_config)
    return space, scout_home


@pytest.fixture
def embed_api_client(
    embed_indexed_space: tuple[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    _, scout_home = embed_indexed_space
    monkeypatch.setattr("scout.api.app.scout_home", lambda: scout_home)
    monkeypatch.setattr("scout.config.scout_home", lambda cwd=None: scout_home)
    return TestClient(create_app(embed_mode=True, warm_cache=False))


@requires_scout_core
def test_search_503_without_embed_or_legacy_index(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.post(
        f"/v1/spaces/{space}/search",
        json={"query": "auth"},
    )
    assert resp.status_code == 503


@requires_scout_core
def test_session_search_empty_before_reads(embed_api_client: TestClient, embed_indexed_space) -> None:
    space, _ = embed_indexed_space
    with patch(
        "scout.api.app.build_provider",
        return_value=AsyncMock(embed=AsyncMock(return_value=[[0.1, 0.2, 0.3, 0.4]])),
    ):
        resp = embed_api_client.post(
            f"/v1/spaces/{space}/search",
            json={"query": "auth"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["hits"] == []
    assert data["session_scoped"] is True


@requires_scout_core
def test_file_read_enqueues_embed_job(embed_api_client: TestClient, embed_indexed_space) -> None:
    space, _ = embed_indexed_space
    from scout.session.queue import EmbedJob, EmbedQueue

    original = EmbedQueue.enqueue
    calls: list[EmbedJob] = []

    def tracking_enqueue(self, job: EmbedJob) -> bool:
        accepted = original(self, job)
        if accepted:
            calls.append(job)
        return accepted

    with patch.object(EmbedQueue, "enqueue", tracking_enqueue), patch(
        "scout.session.worker.SessionEmbedWorker._process",
        new=AsyncMock(),
    ):
        resp = embed_api_client.get(
            f"/v1/spaces/{space}/file",
            params={"rel_path": "src/auth.py"},
        )
        assert resp.status_code == 200
        dup = embed_api_client.get(
            f"/v1/spaces/{space}/file",
            params={"rel_path": "src/auth.py"},
        )
        assert dup.status_code == 200

    assert len(calls) == 1
    assert calls[0].rel_path == "src/auth.py"


@requires_scout_core
def test_graph_cache_serves_symbols_in_embed_mode(
    indexed_api_client: TestClient,
    embed_api_client: TestClient,
    embed_indexed_space,
) -> None:
    space, _ = embed_indexed_space
    baseline = indexed_api_client.get(
        f"/v1/spaces/{space}/symbols",
        params={"path_prefix": "src/"},
    )
    cached = embed_api_client.get(
        f"/v1/spaces/{space}/symbols",
        params={"path_prefix": "src/"},
    )
    assert baseline.status_code == 200
    assert cached.status_code == 200
    assert baseline.json()["symbols"] == cached.json()["symbols"]


@requires_scout_core
def test_session_status_includes_cache_fields(embed_api_client: TestClient, embed_indexed_space) -> None:
    space, _ = embed_indexed_space
    resp = embed_api_client.get(f"/v1/spaces/{space}/session/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "cache_file_count" in data
    assert "cache_bytes" in data
    assert "cache_warm_seconds" in data


@requires_scout_core
def test_session_status_only_in_embed_mode(indexed_api_client: TestClient, indexed_space) -> None:
    space, _ = indexed_space
    resp = indexed_api_client.get(f"/v1/spaces/{space}/session/status")
    assert resp.status_code == 404


@requires_scout_core
def test_search_hit_includes_compressed_text(
    embed_api_client: TestClient,
    embed_indexed_space: tuple[str, Path],
) -> None:
    space, scout_home = embed_indexed_space
    from scout.config import load_config
    from scout.session.store import SessionIndexStore

    config = load_config(scout_home)
    store = SessionIndexStore(scout_home, space, config)
    compressed = "def authenticate(user):\n    return user"
    chunks = [
        {
            "node_id": "test-compress-node",
            "text": compressed,
            "kind": "function",
            "rel_path": "src/auth.py",
            "symbol": "authenticate",
            "start_line": 1,
            "end_line": 2,
        }
    ]
    store.append(chunks, [[0.1, 0.2, 0.3, 0.4]])

    with patch(
        "scout.api.app.build_provider",
        return_value=AsyncMock(embed=AsyncMock(return_value=[[0.1, 0.2, 0.3, 0.4]])),
    ):
        resp = embed_api_client.post(
            f"/v1/spaces/{space}/search",
            json={"query": "auth", "top_k": 5, "min_score": 0.0},
        )
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert len(hits) >= 1
    match = next(h for h in hits if h["node_id"] == "test-compress-node")
    assert match["compressed_text"] == compressed
    assert compressed in match["snippet"] or match["snippet"] in compressed


@requires_scout_core
def test_node_lookup_includes_compressed_text(
    embed_api_client: TestClient,
    embed_indexed_space: tuple[str, Path],
) -> None:
    space, scout_home = embed_indexed_space
    from scout.config import load_config, session_index_path
    from scout.session.store import SessionIndexStore

    symbols = embed_api_client.get(
        f"/v1/spaces/{space}/symbols",
        params={"path_prefix": "src/"},
    ).json()["symbols"]
    node_id = next(s["node_id"] for s in symbols if s.get("symbol") == "authenticate")

    config = load_config(scout_home)
    store = SessionIndexStore(scout_home, space, config)
    body = "def authenticate(user):\n    return user"
    chunks = [
        {
            "node_id": node_id,
            "text": body,
            "kind": "function",
            "rel_path": "src/auth.py",
            "symbol": "authenticate",
            "start_line": 1,
            "end_line": 2,
        }
    ]
    store.append(chunks, [[0.1, 0.2, 0.3, 0.4]])
    assert session_index_path(scout_home, space).exists()

    resp = embed_api_client.get(f"/v1/spaces/{space}/node/{node_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["compressed_text"] == body
    assert data["text"] == body
