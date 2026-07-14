#!/usr/bin/env python3
"""Small Scout API helper for agent terminal sessions."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_SCOUT_API_URL = "http://127.0.0.1:8747/v1"


def _usage() -> int:
    print("usage:", file=sys.stderr)
    print("  scout_api.py spaces list", file=sys.stderr)
    print("  scout_api.py search SPACE QUERY [top_k] [min_score]", file=sys.stderr)
    print("  scout_api.py node SPACE NODE_ID", file=sys.stderr)
    print("  scout_api.py reindex SPACE", file=sys.stderr)
    print("  scout_api.py health", file=sys.stderr)
    print("  scout_api.py METHOD /v1/path [json-body]", file=sys.stderr)
    return 2


def normalize_base_url(url: str) -> str:
    """Ensure base URL ends with /v1 (no trailing slash after v1)."""
    normalized = url.strip().rstrip("/")
    if not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    return normalized


def resolve_api_path(base_url: str, path: str) -> str:
    """Join base URL with an API path, avoiding duplicate /v1 segments."""
    if not path.startswith("/"):
        path = "/" + path
    if path.startswith("/v1/"):
        path = path[3:]
    elif path == "/v1":
        path = "/"
    return f"{base_url}{path}"


def _config() -> tuple[str, str]:
    token = os.environ.get("SCOUT_API_TOKEN", "").strip()
    env_url = os.environ.get("SCOUT_API_URL", "").strip()
    if env_url:
        return normalize_base_url(env_url), token

    from pathlib import Path

    config_path = Path.home() / ".scout" / "config.yaml"
    if config_path.exists():
        import yaml

        with config_path.open(encoding="utf-8") as handle:
            cfg = yaml.safe_load(handle) or {}
        config_url = str(cfg.get("api_base_url", "") or "").strip()
        if config_url:
            return normalize_base_url(config_url), token

    return DEFAULT_SCOUT_API_URL, token


def _request(method: str, url: str, body: str | None, token: str) -> int:
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            print(f"invalid json body: {exc}", file=sys.stderr)
            return 2
        data = json.dumps(parsed).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = resp.read().decode("utf-8")
            try:
                parsed = json.loads(result)
                print(json.dumps(parsed, indent=2))
            except json.JSONDecodeError:
                print(result)
            return 0
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        print(text or f"HTTP {exc.code}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    if len(sys.argv) < 2:
        return _usage()

    base_url, token = _config()

    command = sys.argv[1].lower()

    if command == "health":
        return _request("GET", resolve_api_path(base_url, "/health"), None, token)

    if command == "spaces" and len(sys.argv) >= 3 and sys.argv[2].lower() == "list":
        return _request("GET", resolve_api_path(base_url, "/spaces/list"), None, token)

    if command == "search" and len(sys.argv) >= 4:
        space = sys.argv[2]
        query = sys.argv[3]
        top_k = int(sys.argv[4]) if len(sys.argv) >= 5 else 10
        min_score = float(sys.argv[5]) if len(sys.argv) >= 6 else 0.0
        body = json.dumps({"query": query, "top_k": top_k, "min_score": min_score})
        return _request(
            "POST",
            resolve_api_path(base_url, f"/spaces/{space}/search"),
            body,
            token,
        )

    if command == "node" and len(sys.argv) >= 4:
        space = sys.argv[2]
        node_id = sys.argv[3]
        return _request(
            "GET",
            resolve_api_path(base_url, f"/spaces/{space}/node/{node_id}"),
            None,
            token,
        )

    if command == "reindex" and len(sys.argv) >= 3:
        space = sys.argv[2]
        return _request(
            "POST",
            resolve_api_path(base_url, f"/spaces/{space}/reindex"),
            None,
            token,
        )

    if len(sys.argv) < 3:
        return _usage()

    method = sys.argv[1].upper()
    path = sys.argv[2]
    body = sys.argv[3] if len(sys.argv) > 3 else None
    return _request(method, resolve_api_path(base_url, path), body, token)


if __name__ == "__main__":
    raise SystemExit(main())
