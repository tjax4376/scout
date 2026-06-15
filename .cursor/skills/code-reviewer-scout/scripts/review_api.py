#!/usr/bin/env python3
"""Scout REST helper for code review — graph map + on-demand read.

Metadata: v0.1.2 | Scout Contributors | 2026-06-14
Change rationale: Symbols-first review — map (symbols) before file read.
Uses stdlib only; no Scout Python package dependency at runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def resolve_base_url() -> str | None:
    """Resolve Scout API base URL (includes /v1) from env or ~/.scout/config.yaml."""
    base_url = os.environ.get("SCOUT_API_URL", "").strip().rstrip("/")
    if not base_url:
        try:
            import yaml
        except ImportError:
            yaml = None  # type: ignore[assignment]
        config_path = Path.home() / ".scout" / "config.yaml"
        if yaml is not None and config_path.exists():
            with config_path.open(encoding="utf-8") as handle:
                cfg = yaml.safe_load(handle) or {}
            base_url = str(cfg.get("api_base_url", "")).strip().rstrip("/")
    if not base_url:
        print(
            "missing SCOUT_API_URL; set it or ensure ~/.scout/config.yaml has api_base_url",
            file=sys.stderr,
        )
        return None
    return base_url


def resolve_token() -> str:
    return os.environ.get("SCOUT_API_TOKEN", "").strip()


def build_search_url(base_url: str, space: str) -> str:
    return f"{base_url}/spaces/{space}/search"


def build_node_url(base_url: str, space: str, node_id: str) -> str:
    return f"{base_url}/spaces/{space}/node/{node_id}"


def build_neighbors_url(
    base_url: str,
    space: str,
    node_id: str,
    *,
    depth: int,
    max_nodes: int,
) -> str:
    qs = urllib.parse.urlencode({"depth": depth, "max_nodes": max_nodes})
    return f"{base_url}/spaces/{space}/node/{node_id}/neighbors?{qs}"


def build_symbols_url(
    base_url: str,
    space: str,
    path_prefix: str,
    kinds: list[str] | None = None,
) -> str:
    params: list[tuple[str, str]] = [("path_prefix", path_prefix)]
    if kinds:
        for kind in kinds:
            params.append(("kinds", kind))
    qs = urllib.parse.urlencode(params)
    return f"{base_url}/spaces/{space}/symbols?{qs}"


def build_file_url(
    base_url: str,
    space: str,
    rel_path: str,
    *,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    params: dict[str, str | int] = {"rel_path": rel_path}
    if start_line is not None:
        params["start_line"] = start_line
    if end_line is not None:
        params["end_line"] = end_line
    qs = urllib.parse.urlencode(params)
    return f"{base_url}/spaces/{space}/file?{qs}"


def build_search_body(
    query: str,
    *,
    top_k: int = 5,
    min_score: float = 0.0,
    path_prefix: str | None = None,
    kinds: list[str] | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "query": query,
        "top_k": top_k,
        "min_score": min_score,
    }
    if path_prefix:
        body["path_prefix"] = path_prefix
    if kinds:
        body["kinds"] = kinds
    return body


def http_request(method: str, url: str, body: dict[str, object] | None, token: str) -> tuple[int, str]:
    """Perform HTTP request; return (exit_code, output_text)."""
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return 0, json.dumps(json.loads(raw), indent=2)
            except json.JSONDecodeError:
                return 0, raw
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return 1, text or f"HTTP {exc.code}"
    except OSError as exc:
        return 1, f"request failed: {exc}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scout REST helper for code review (map symbols first, then read)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="GET /health")
    sub.add_parser("spaces-list", help="GET /spaces/list")

    search_p = sub.add_parser("search", help="POST /spaces/{space}/search")
    search_p.add_argument("space", help="Scout space name")
    search_p.add_argument("query", help="Search query text")
    search_p.add_argument("--path-prefix", default=None, help="Limit to rel_path prefix")
    search_p.add_argument("--kinds", default=None, help="Comma-separated kinds filter")
    search_p.add_argument("--top-k", type=int, default=5, help="Max hits (default 5)")
    search_p.add_argument("--min-score", type=float, default=0.0, help="Min similarity score")

    symbols_p = sub.add_parser("symbols", help="GET /spaces/{space}/symbols")
    symbols_p.add_argument("space", help="Scout space name")
    symbols_p.add_argument("path_prefix", help="rel_path prefix to list")
    symbols_p.add_argument("--kinds", default=None, help="Comma-separated kinds filter")

    map_p = sub.add_parser(
        "map",
        help="GET /spaces/{space}/symbols (alias — run before file read)",
    )
    map_p.add_argument("space", help="Scout space name")
    map_p.add_argument("path_prefix", help="rel_path prefix to list")
    map_p.add_argument("--kinds", default=None, help="Comma-separated kinds filter")

    neighbors_p = sub.add_parser("neighbors", help="GET /spaces/{space}/node/{id}/neighbors")
    neighbors_p.add_argument("space", help="Scout space name")
    neighbors_p.add_argument("node_id", help="Node ID from symbols or search")
    neighbors_p.add_argument("--depth", type=int, default=3, help="BFS depth (1-5)")
    neighbors_p.add_argument("--max-nodes", type=int, default=50, help="Max neighbors")

    node_p = sub.add_parser("node", help="GET /spaces/{space}/node/{node_id} (full text)")
    node_p.add_argument("space", help="Scout space name")
    node_p.add_argument("node_id", help="16-char hex node ID")

    file_p = sub.add_parser("file", help="GET /spaces/{space}/file")
    file_p.add_argument("space", help="Scout space name")
    file_p.add_argument("rel_path", help="File path relative to space root")
    file_p.add_argument("--start-line", type=int, default=None)
    file_p.add_argument("--end-line", type=int, default=None)

    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base_url = resolve_base_url()
    if base_url is None:
        return 2
    token = resolve_token()

    if args.command == "health":
        code, out = http_request("GET", f"{base_url}/health", None, token)
    elif args.command == "spaces-list":
        code, out = http_request("GET", f"{base_url}/spaces/list", None, token)
    elif args.command == "search":
        kinds = [k.strip() for k in args.kinds.split(",") if k.strip()] if args.kinds else None
        body = build_search_body(
            args.query,
            top_k=args.top_k,
            min_score=args.min_score,
            path_prefix=args.path_prefix,
            kinds=kinds,
        )
        code, out = http_request("POST", build_search_url(base_url, args.space), body, token)
    elif args.command in ("symbols", "map"):
        kinds = [k.strip() for k in args.kinds.split(",") if k.strip()] if args.kinds else None
        url = build_symbols_url(base_url, args.space, args.path_prefix, kinds)
        code, out = http_request("GET", url, None, token)
    elif args.command == "neighbors":
        url = build_neighbors_url(
            base_url,
            args.space,
            args.node_id,
            depth=args.depth,
            max_nodes=args.max_nodes,
        )
        code, out = http_request("GET", url, None, token)
    elif args.command == "node":
        code, out = http_request("GET", build_node_url(base_url, args.space, args.node_id), None, token)
    elif args.command == "file":
        url = build_file_url(
            base_url,
            args.space,
            args.rel_path,
            start_line=args.start_line,
            end_line=args.end_line,
        )
        code, out = http_request("GET", url, None, token)
    else:
        return 2

    stream = sys.stdout if code == 0 else sys.stderr
    print(out, file=stream)
    return code


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
