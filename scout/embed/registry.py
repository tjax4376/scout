"""Embed provider registry — Python-only HTTP clients.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

from __future__ import annotations

import socket
from abc import ABC, abstractmethod
from typing import Any

import httpx

LOCAL_PROVIDER_WARNING = (
    "Use an embedding/tool model, not a chat model. "
    "Wrong model type will produce poor search results."
)

DEFAULT_PORTS = {
    "lmstudio": 1234,
    "omlx": 8080,
    "unsloth-studio": 8000,
}


class EmbedProvider(ABC):
    name: str

    @abstractmethod
    async def list_models(self) -> list[str]:
        ...

    @abstractmethod
    async def probe_dimensions(self, model: str) -> int:
        ...

    @abstractmethod
    async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        ...


class OpenRouterProvider(EmbedProvider):
    name = "openrouter"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base = "https://openrouter.ai/api/v1"

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        models = []
        for item in data.get("data", []):
            mid = item.get("id", "")
            # Filter embed-capable models heuristically.
            if any(k in mid.lower() for k in ("embed", "bge", "e5", "minilm")):
                models.append(mid)
        return models or [m.get("id", "") for m in data.get("data", [])[:20] if m.get("id")]

    async def probe_dimensions(self, model: str) -> int:
        vecs = await self.embed(model, ["dimension probe"])
        return len(vecs[0])

    async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "input": texts},
            )
            resp.raise_for_status()
            payload = resp.json()
        return [item["embedding"] for item in payload.get("data", [])]


class OpenAICompatProvider(EmbedProvider):
    """Local providers exposing OpenAI-compatible /v1 API."""

    def __init__(self, name: str, endpoint: str) -> None:
        self.name = name
        self.endpoint = endpoint.rstrip("/")

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.endpoint}/models")
            resp.raise_for_status()
            data = resp.json()
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]

    async def probe_dimensions(self, model: str) -> int:
        vecs = await self.embed(model, ["dimension probe"])
        return len(vecs[0])

    async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.endpoint}/embeddings",
                json={"model": model, "input": texts},
            )
            resp.raise_for_status()
            payload = resp.json()
        return [item["embedding"] for item in payload.get("data", [])]


def build_provider(
    name: str,
    *,
    api_key: str | None = None,
    endpoint: str | None = None,
) -> EmbedProvider:
    if name == "openrouter":
        if not api_key:
            raise ValueError("openrouter requires API key")
        return OpenRouterProvider(api_key)
    if name in {"lmstudio", "omlx", "unsloth-studio"}:
        if not endpoint:
            raise ValueError(f"{name} requires endpoint")
        return OpenAICompatProvider(name, endpoint)
    raise ValueError(f"unknown embed provider: {name}")


def is_local_provider(name: str) -> bool:
    return name in {"lmstudio", "omlx", "unsloth-studio"}


async def scan_local_endpoint(host: str, start_port: int, end_port: int) -> str | None:
    """Scan port range and probe GET /v1/models."""
    async with httpx.AsyncClient(timeout=2) as client:
        for port in range(start_port, end_port + 1):
            if not _port_open(host, port):
                continue
            url = f"http://{host}:{port}/v1"
            try:
                resp = await client.get(f"{url}/models")
                if resp.status_code == 200:
                    return url
            except httpx.HTTPError:
                continue
    return None


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def find_free_api_port(start: int = 8741, end: int = 8799) -> int:
    for port in range(start, end + 1):
        if not _port_open("127.0.0.1", port):
            return port
    raise RuntimeError("no free API port found in range")


async def filter_embed_models(provider: EmbedProvider, models: list[str]) -> list[str]:
    """Prefer models that look embed-capable."""
    filtered = [
        m
        for m in models
        if any(k in m.lower() for k in ("embed", "bge", "e5", "minilm", "nomic"))
    ]
    return filtered or models
