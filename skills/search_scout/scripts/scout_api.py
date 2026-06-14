#!/usr/bin/env python3
"""Small Scout API helper for agent terminal sessions."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _usage() -> int:
    print("usage:", file=sys.stderr)
    print("  scout_api.py spaces list", file=sys.stderr)
    print("  scout_api.py search SPACE QUERY [top_k] [min_score]", file=sys.stderr)
    print("  scout_api.py node SPACE NODE_ID", file=sys.stderr)
    print("  scout_api.py reindex SPACE", file=sys.stderr)
    print("  scout_api.py health", file=sys.stderr)
    print("  scout_api.py METHOD /v1/path [json-body]", file=sys.stderr)
    return 2


def _config() -> tuple[str, str] | None:
    base_url = os.environ.get("SCOUT_API_URL", "").strip().rstrip("/")
    if not base_url:
        # Try to read from scout config
        import yaml
        from pathlib import Path
        scout_home = Path.home() / ".scout"
        config_path = scout_home / "config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            base_url = cfg.get("api_base_url", "").strip().rstrip("/")
    token = os.environ.get("SCOUT_API_TOKEN", "").strip()
    if not base_url:
        print("missing SCOUT_API_URL; set it or ensure ~/.scout/config.yaml has api_base_url", file=sys.stderr)
        return None
    return base_url, token


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
            # Pretty-print JSON
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

    config = _config()
    if config is None:
        return 2
    base_url, token = config

    command = sys.argv[1].lower()

    if command == "health":
        return _request("GET", f"{base_url}/v1/health", None, token)

    elif command == "spaces" and len(sys.argv) >= 3 and sys.argv[2].lower() == "list":
        return _request("GET", f"{base_url}/v1/spaces/list", None, token)

    elif command == "search" and len(sys.argv) >= 4:
        space = sys.argv[2]
        query = sys.argv[3]
        top_k = int(sys.argv[4]) if len(sys.argv) >= 5 else 10
        min_score = float(sys.argv[5]) if len(sys.argv) >= 6 else 0.0
        body = json.dumps({"query": query, "top_k": top_k, "min_score": min_score})
        return _request("POST", f"{base_url}/v1/spaces/{space}/search", body, token)

    elif command == "node" and len(sys.argv) >= 4:
        space = sys.argv[2]
        node_id = sys.argv[3]
        return _request("GET", f"{base_url}/v1/spaces/{space}/node/{node_id}", None, token)

    elif command == "reindex" and len(sys.argv) >= 3:
        space = sys.argv[2]
        return _request("POST", f"{base_url}/v1/spaces/{space}/reindex", None, token)

    else:
        # Generic: METHOD /v1/path [json-body]
        if len(sys.argv) < 3:
            return _usage()
        method = sys.argv[1].upper()
        path = sys.argv[2]
        if not path.startswith("/"):
            path = "/" + path
        body = sys.argv[3] if len(sys.argv) > 3 else None
        return _request(method, f"{base_url}{path}", body, token)


if __name__ == "__main__":
    raise SystemExit(main())
