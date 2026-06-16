"""Scout REST client with Hawkeye session tracing.

Metadata: v1.0.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from scout.hawkeye.trace.store import TraceStore, content_hash


class ScoutTraceClient:
    """HTTP client for Scout API that logs investigation steps."""

    def __init__(
        self,
        base_url: str,
        space: str,
        session_id: str,
        trace: TraceStore,
        *,
        token: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.space = space
        self.session_id = session_id
        self.trace = trace
        self.token = token
        self.stale = False

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-Hawkeye-Session-Id": self.session_id,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = self._headers()
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
                stale_hdr = resp.headers.get("X-Scout-Stale", "false")
                self.stale = stale_hdr.lower() == "true"
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Scout API {exc.code}: {detail}") from exc

    def list_symbols(self, path_prefix: str = "") -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if path_prefix:
            params["path_prefix"] = path_prefix
        qs = urllib.parse.urlencode(params)
        path = f"/spaces/{urllib.parse.quote(self.space)}/symbols"
        if qs:
            path = f"{path}?{qs}"
        payload = self._request("GET", path)
        symbols = list(payload.get("symbols") or [])
        self.trace.log_step(
            "symbols",
            path_prefix=path_prefix,
            symbol_count=len(symbols),
            stale=self.stale,
        )
        return symbols

    def neighbors(self, node_id: str, *, depth: int = 2, max_nodes: int = 50) -> list[dict[str, Any]]:
        qs = urllib.parse.urlencode({"depth": depth, "max_nodes": max_nodes})
        path = f"/spaces/{urllib.parse.quote(self.space)}/node/{urllib.parse.quote(node_id)}/neighbors?{qs}"
        payload = self._request("GET", path)
        neighbors = list(payload.get("neighbors") or [])
        edge_kinds = sorted({str(n.get("edge") or "") for n in neighbors})
        self.trace.log_step(
            "neighbors",
            node_id=node_id,
            depth=depth,
            max_nodes=max_nodes,
            neighbor_count=len(neighbors),
            edge_kinds=edge_kinds,
            stale=self.stale,
        )
        return neighbors

    def read_file(
        self,
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
        path = f"/spaces/{urllib.parse.quote(self.space)}/file?{qs}"
        payload = self._request("GET", path)
        text = str(payload.get("text") or "")
        self.trace.log_step(
            "file_read",
            rel_path=rel_path,
            start_line=start_line,
            end_line=end_line,
            content_hash=content_hash(text),
            stale=self.stale,
        )
        return text
