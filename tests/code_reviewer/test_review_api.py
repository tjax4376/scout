"""review_api.py URL and body construction tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

_SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "code-reviewer-scout" / "scripts" / "review_api.py"
_spec = importlib.util.spec_from_file_location("review_api", _SCRIPT)
assert _spec and _spec.loader
review_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(review_api)


def test_build_search_url() -> None:
    url = review_api.build_search_url("http://127.0.0.1:8741/v1", "myapp")
    assert url == "http://127.0.0.1:8741/v1/spaces/myapp/search"


def test_build_node_url() -> None:
    url = review_api.build_node_url("http://127.0.0.1:8741/v1", "myapp", "abc123")
    assert url == "http://127.0.0.1:8741/v1/spaces/myapp/node/abc123"


def test_build_search_body_with_path_prefix_and_kinds() -> None:
    body = review_api.build_search_body(
        "auth middleware",
        top_k=5,
        path_prefix="src/api/",
        kinds=["function", "method"],
    )
    assert body["query"] == "auth middleware"
    assert body["top_k"] == 5
    assert body["path_prefix"] == "src/api/"
    assert body["kinds"] == ["function", "method"]


def test_run_search_posts_to_correct_url() -> None:
    captured: dict[str, object] = {}

    def fake_http(method: str, url: str, body: dict | None, token: str) -> tuple[int, str]:
        captured["method"] = method
        captured["url"] = url
        captured["body"] = body
        return 0, "{}"

    with patch.object(review_api, "resolve_base_url", return_value="http://127.0.0.1:8741/v1"):
        with patch.object(review_api, "http_request", side_effect=fake_http):
            code = review_api.run(
                [
                    "search",
                    "myapp",
                    "token validation",
                    "--path-prefix",
                    "src/",
                    "--kinds",
                    "function",
                    "--top-k",
                    "3",
                ]
            )
    assert code == 0
    assert captured["method"] == "POST"
    assert captured["url"] == "http://127.0.0.1:8741/v1/spaces/myapp/search"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["path_prefix"] == "src/"
    assert body["kinds"] == ["function"]
    assert body["top_k"] == 3


def test_run_missing_base_url_exits_2() -> None:
    with patch.object(review_api, "resolve_base_url", return_value=None):
        assert review_api.run(["health"]) == 2


def test_parse_args_search() -> None:
    args = review_api.parse_args(["search", "space", "query", "--path-prefix", "pkg/"])
    assert args.command == "search"
    assert args.space == "space"
    assert args.path_prefix == "pkg/"
