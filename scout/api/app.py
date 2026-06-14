"""FastAPI REST API for Scout.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import scout_core
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

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
    validate_embed,
    validate_space,
)
from scout.embed.registry import build_provider
from scout.indexing import run_reindex

app = FastAPI(title="Scout API", version="0.1.0", openapi_url="/v1/openapi.json")


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
async def search_space(space: str, body: SearchRequest, response: Response) -> dict[str, Any]:
    _require_core()
    home = _home()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")

    entry = validate_space(home, space)
    embed = validate_embed(config)
    stale, index_version = scout_core.py_check_staleness(
        entry.root,
        str(manifest_path(home, space)),
        embed.provider,
        embed.model,
        embed.dimensions,
        entry.skip_globs,
        entry.skip_paths,
    )

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
    response.headers["X-Scout-Stale"] = str(stale).lower()
    response.headers["X-Scout-Index-Version"] = index_version
    return json.loads(raw)


@app.get("/v1/spaces/{space}/node/{node_id}")
def get_node(space: str, node_id: str, response: Response) -> dict[str, Any]:
    _require_core()
    home = _home()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")

    entry = validate_space(home, space)
    embed = validate_embed(config)
    stale, index_version = scout_core.py_check_staleness(
        entry.root,
        str(manifest_path(home, space)),
        embed.provider,
        embed.model,
        embed.dimensions,
        entry.skip_globs,
        entry.skip_paths,
    )
    try:
        raw = scout_core.py_get_node(
            str(graph_bin_path(home, space)),
            str(index_db_path(home, space)),
            node_id,
        )
    except Exception as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise
    response.headers["X-Scout-Stale"] = str(stale).lower()
    response.headers["X-Scout-Index-Version"] = index_version
    return json.loads(raw)


@app.post("/v1/spaces/{space}/reindex")
async def reindex_space(space: str) -> dict[str, str]:
    _require_core()
    home = bootstrap_scout_dir()
    config = load_config(home)
    if space not in config.spaces:
        raise HTTPException(status_code=404, detail=f"unknown space: {space}")
    embed = validate_embed(config)
    secrets = load_secrets(home)
    provider = build_provider(
        embed.provider,
        api_key=get_embed_api_key(secrets, embed.provider),
        endpoint=embed.endpoint or None,
    )
    try:
        version = await run_reindex(home, space, config, provider)
    except RuntimeError as exc:
        if "reindex in progress" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"index_version": version, "status": "ok"}


def create_app() -> FastAPI:
    return app
