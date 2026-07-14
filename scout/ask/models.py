"""Pydantic models for POST /v1/spaces/{space}/ask.

Metadata: v0.1.0 | Scout Contributors | 2026-07-14
Change rationale: ask-scout-structure — request/response shapes for graph ask.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskStructureRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    top_k: int = Field(default=10, ge=1, le=50)
    expand_depth: int = Field(default=1, ge=0, le=2)
    max_nodes: int = Field(default=50, ge=1, le=200)
    path_prefix: str | None = Field(default=None, max_length=1000)


class AskStructureResponse(BaseModel):
    query: str
    hits: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    total: int
    mode: str = "graph"
    truncated: bool = False
