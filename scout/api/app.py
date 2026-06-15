"""FastAPI REST API for Scout.

Metadata: v0.1.0 | Scout Contributors | 2026-06-14
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import scout_core
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from scout.api.graph_file import aggregate_file_graph
from scout.config import (
    ScoutConfig,
    bootstrap_scout_dir,
    get_embed_api_key,
    graph_bin_path,
    index_db_path,
    load_config,
    load_secrets,
    manifest_path,
    scout_home,
    session_index_path,
    validate_embed,
    validate_space,
)
from scout.embed.registry import build_provider
from scout.graph_find import graph_path_search
from scout.indexing import run_reindex
from scout.session.runtime import SessionRuntime


@asynccontextmanager
async def _lifespan(fastapi_app: FastAPI):
    yield
    runtime: SessionRuntime | None = getattr(fastapi_app.state, "session_runtime", None)
    if runtime is not None:
        runtime.shutdown()


app = FastAPI(
    title="Scout API",
    version="0.1.0",
    openapi_url="/v1/openapi.json",
    lifespan=_lifespan,
)
app.state.embed_mode = False
app.state.session_runtime = None

_GRAPH_WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "graph"


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    kinds: list[str] | None = None
    path_prefix: str | None = None


class SpaceInfo(BaseModel):
    name: str
    root: str
    skip_globs: list[str] = Field(default_factory=list)
    skip_paths: list[str] = Field(default_factory=list)


class SpaceListResponse(BaseModel):
    spaces: list[SpaceInfo]


def _home() -> Path:
    return scout_home()


def _require_core() -> None:
    if scout_core is None:
        raise HTTPException(status_code=500, detail="scout_core not installed")


def _staleness(space: str, home: Path, config: ScoutConfig) -> tuple[bool, str]:
    entry = validate_space(home, space)
    embed = config.embed
    return scout_core.py_check_staleness(
        entry.root,
        str(manifest_path(home, space)),
        embed.provider or "",
        embed.model or "",
        embed.dimensions or 0,
        entry.skip_globs,
        entry.skip_paths,
        entry.respect_gitignore,
    )


def _set_staleness_headers(response: Response, stale: bool, index_version: str) -> None:
    response.headers["X-Scout-Stale"] = str(stale).lower()
    response.headers["X-Scout-Index-Version"] = index_version


def _session_runtime(request: Request) -> SessionRuntime | None:
    return getattr(request.app.state, "session_runtime", None)


def _embed_mode(request: Request) -> bool:
    return bool(getattr(request.app.state, "embed_mode", False))


def _legacy_index_available(home: Path, space: str) -> bool:
    return scout_core.py_index_exists(str(index_db_path(home, space)))


def _map_scout_core_error(exc: Exception) -> HTTPException:
    msg = str(exc)
    lower = msg.lower()
    name = type(exc).__name__
    if "payload too large" in lower or "response exceeds" in lower:
        return HTTPException(status_code=413, detail=msg)
    if (
        "path traversal" in lower
        or "invalid path" in lower
        or "outside space root" in lower
        or "rel_path is required" in lower
        or "start_line" in lower
    ):
        return HTTPException(status_code=400, detail=msg)
    if "not found" in lower or name in {"FileNotFoundError", "PyFileNotFoundError"}:
        return HTTPException(status_code=404, detail=msg)
    return HTTPException(status_code=500, detail=msg)


@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/spaces/list", response_model=SpaceListResponse)
def list_spaces() -> SpaceListResponse:
    config = load_config(_home())
    spaces = [
        SpaceInfo(
            name=entry.name,
            root=entry.root,
            skip_globs=entry.skip_globs,
            skip_paths=entry.skip_paths,
        )
        for entry in sorted(config.spaces.values(), key=lambda e: e.name)
    ]
    return SpaceListResponse(spaces=spaces)


@app.post("/v1/spaces/{space}/search")
async def search_space(
    space: str,
    body: SearchRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    _require_core()
    home = _home()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")

    runtime = _session_runtime(request)
    embed_mode = _embed_mode(request)
    stale, index_version = _staleness(space, home, config)

    if embed_mode:
        if runtime is None or not runtime.embed_ready:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "embed provider not configured; run setup with embed or use graph endpoints",
                },
            )
        store = runtime.store_for(space)
        if store is None or not store.exists():
            _set_staleness_headers(response, stale, index_version)
            return {"hits": [], "stale": stale, "index_version": index_version, "session_scoped": True}

        embed = validate_embed(config)
        secrets = load_secrets(home)
        provider = build_provider(
            embed.provider,
            api_key=get_embed_api_key(secrets, embed.provider),
            endpoint=embed.endpoint or None,
        )
        query_vec = (await provider.embed(embed.model, [body.query]))[0]
        raw = scout_core.py_search(
            str(graph_bin_path(home, space)),
            str(session_index_path(home, space)),
            query_vec,
            body.top_k,
            body.min_score,
            body.kinds,
            body.path_prefix,
            stale,
            index_version,
        )
        payload = json.loads(raw)
        payload["session_scoped"] = True
        _set_staleness_headers(response, stale, index_version)
        return payload

    if not _legacy_index_available(home, space):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "vector index not available; use /symbols, /neighbors, and /file, or scout serve --embed",
            },
        )

    embed = validate_embed(config)
    secrets = load_secrets(home)
    provider = build_provider(
        embed.provider,
        api_key=get_embed_api_key(secrets, embed.provider),
        endpoint=embed.endpoint or None,
    )
    query_vec = (await provider.embed(embed.model, [body.query]))[0]

    raw = scout_core.py_search(
        str(graph_bin_path(home, space)),
        str(index_db_path(home, space)),
        query_vec,
        body.top_k,
        body.min_score,
        body.kinds,
        body.path_prefix,
        stale,
        index_version,
    )
    _set_staleness_headers(response, stale, index_version)
    return json.loads(raw)


@app.get("/v1/spaces/{space}/node/{node_id}")
def get_node(
    space: str,
    node_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    _require_core()
    home = _home()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")

    stale, index_version = _staleness(space, home, config)
    db_path = index_db_path(home, space)
    if _embed_mode(request):
        db_path = session_index_path(home, space)
    try:
        raw = scout_core.py_get_node(
            str(graph_bin_path(home, space)),
            str(db_path),
            node_id,
        )
    except Exception as exc:
        raise _map_scout_core_error(exc) from exc
    _set_staleness_headers(response, stale, index_version)
    return json.loads(raw)


@app.get("/v1/spaces/{space}/node/{node_id}/neighbors")
def get_neighbors(
    space: str,
    node_id: str,
    request: Request,
    response: Response,
    depth: int = Query(default=3, ge=1, le=5),
    max_nodes: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    _require_core()
    home = _home()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")

    stale, index_version = _staleness(space, home, config)
    runtime = _session_runtime(request)
    if _embed_mode(request) and runtime is not None:
        try:
            payload = runtime.graph_cache.expand_neighbors(space, node_id, depth, max_nodes)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"not found: {node_id}") from exc
        _set_staleness_headers(response, stale, index_version)
        return payload

    try:
        raw = scout_core.py_expand_neighbors(
            str(graph_bin_path(home, space)),
            node_id,
            depth,
            max_nodes,
        )
    except Exception as exc:
        raise _map_scout_core_error(exc) from exc
    _set_staleness_headers(response, stale, index_version)
    return json.loads(raw)


@app.get("/v1/spaces/{space}/graph/search")
def graph_search(
    space: str,
    response: Response,
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    _require_core()
    home = _home()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")

    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="empty search query")

    try:
        payload = graph_path_search(
            home,
            space,
            config,
            query,
            top_k=top_k,
            dedupe_by_path=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    stale = bool(payload.get("stale"))
    index_version = str(payload.get("index_version") or "")
    _set_staleness_headers(response, stale, index_version)
    return payload


@app.get("/v1/spaces/{space}/graph/file")
def graph_file(
    space: str,
    response: Response,
    rel_path: str = Query(..., min_length=1),
    max_nodes: int = Query(default=200, ge=1, le=200),
) -> dict[str, Any]:
    _require_core()
    home = _home()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")

    entry = validate_space(home, space)
    stale, index_version = _staleness(space, home, config)

    try:
        scout_core.py_read_workspace_file(entry.root, rel_path, 1, 1)
    except Exception as exc:
        raise _map_scout_core_error(exc) from exc

    graph_path = graph_bin_path(home, space)
    if not graph_path.exists():
        raise HTTPException(
            status_code=404,
            detail="graph index not found; run scout <space> reindex",
        )

    payload = aggregate_file_graph(
        str(graph_path),
        rel_path,
        max_nodes=max_nodes,
    )
    _set_staleness_headers(response, stale, index_version)
    return payload


@app.get("/v1/spaces/{space}/symbols")
def list_symbols(
    space: str,
    request: Request,
    response: Response,
    path_prefix: str = Query(default="", min_length=0),
    kinds: list[str] | None = Query(default=None),
) -> dict[str, Any]:
    _require_core()
    home = _home()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")

    stale, index_version = _staleness(space, home, config)
    runtime = _session_runtime(request)
    if _embed_mode(request) and runtime is not None:
        payload = runtime.graph_cache.list_symbols(space, path_prefix, kinds)
        _set_staleness_headers(response, stale, index_version)
        return payload

    raw = scout_core.py_list_symbols(
        str(graph_bin_path(home, space)),
        path_prefix,
        kinds,
    )
    _set_staleness_headers(response, stale, index_version)
    return json.loads(raw)


@app.get("/v1/spaces/{space}/file")
def read_file(
    space: str,
    request: Request,
    response: Response,
    rel_path: str = Query(..., min_length=1),
    start_line: int | None = Query(default=None, ge=1),
    end_line: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    _require_core()
    home = _home()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")

    entry = validate_space(home, space)
    stale, index_version = _staleness(space, home, config)
    root = Path(entry.root)
    runtime = _session_runtime(request)
    payload: dict[str, Any] | None = None
    if runtime is not None:
        cache = runtime.file_cache(space)
        if cache is not None:
            try:
                payload = cache.read_response(root, rel_path, start_line, end_line)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload is None:
        try:
            raw = scout_core.py_read_workspace_file(
                entry.root,
                rel_path,
                start_line,
                end_line,
            )
        except Exception as exc:
            raise _map_scout_core_error(exc) from exc
        payload = json.loads(raw)
        if runtime is not None:
            cache = runtime.file_cache(space)
            if cache is not None and start_line is None and end_line is None:
                try:
                    mtime = int((root / rel_path).stat().st_mtime)
                except OSError:
                    mtime = 0
                cache.put(rel_path, str(payload["text"]), mtime)

    if _embed_mode(request) and runtime is not None:
        runtime.enqueue_file_read(space, rel_path, start_line, end_line)

    _set_staleness_headers(response, stale, index_version)
    return payload


@app.get("/v1/spaces/{space}/session/status")
def session_status(space: str, request: Request) -> dict[str, Any]:
    if not _embed_mode(request):
        raise HTTPException(status_code=404, detail="session embed mode not active")
    runtime = _session_runtime(request)
    if runtime is None:
        raise HTTPException(status_code=503, detail="session runtime unavailable")
    home = _home()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")
    return runtime.status(space)


@app.delete("/v1/spaces/{space}/session/index")
def clear_session_index(space: str, request: Request) -> dict[str, str]:
    if not _embed_mode(request):
        raise HTTPException(status_code=404, detail="session embed mode not active")
    runtime = _session_runtime(request)
    if runtime is None:
        raise HTTPException(status_code=503, detail="session runtime unavailable")
    home = _home()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")
    try:
        runtime.clear_index(space)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "cleared"}


@app.post("/v1/spaces/{space}/reindex")
async def reindex_space(space: str) -> dict[str, str]:
    _require_core()
    home = bootstrap_scout_dir()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")
    try:
        version = await run_reindex(home, space, config)
    except RuntimeError as exc:
        if "reindex in progress" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"index_version": version, "status": "ok"}


def create_app(embed_mode: bool = False, warm_cache: bool = True) -> FastAPI:
    prev: SessionRuntime | None = getattr(app.state, "session_runtime", None)
    if prev is not None:
        prev.shutdown()
    app.state.embed_mode = embed_mode
    app.state.session_runtime = None
    if embed_mode:
        home = scout_home()
        config = load_config(home)
        runtime = SessionRuntime(home, config)
        try:
            runtime.start(warm_cache=warm_cache)
        except RuntimeError as exc:
            if "not enough capacity" in str(exc):
                raise RuntimeError(str(exc)) from exc
            raise
        app.state.session_runtime = runtime
    return app


if _GRAPH_WEB_DIR.is_dir():
    app.mount(
        "/graph",
        StaticFiles(directory=str(_GRAPH_WEB_DIR), html=True),
        name="graph-ui",
    )
