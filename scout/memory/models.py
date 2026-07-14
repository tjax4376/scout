"""Pydantic models for the memory API.

Metadata: v0.1.0 | Scout Contributors | 2026-07-13
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MemoryCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1, max_length=50000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    category: str | None = Field(default=None, max_length=100)


class MemoryResponse(BaseModel):
    id: str
    title: str
    body: str
    category: str
    tags: list[str]
    created_at: str
    space: str
    rel_path: str


class CategoryRecommendation(BaseModel):
    suggested_categories: list[str] = Field(default_factory=list)


class MemoryListResponse(BaseModel):
    memories: list[dict[str, Any]]
    total: int


class AskMemoryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)


class AskMemoryResponse(BaseModel):
    memories: list[dict[str, Any]]
    total: int
    query: str
