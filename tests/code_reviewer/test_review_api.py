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


def test_build_symbols_url() -> None:
    url = review_api.build_symbols_url(
        "http://127.0.0.1:8741/v1",
        "myapp",
        "scout/embed/",
        ["function"],
    )
    assert "/spaces/myapp/symbols?" in url
    assert "path_prefix=scout%2Fembed%2F" in url
    assert "kinds=function" in url


def test_build_neighbors_url() -> None:
    url = review_api.build_neighbors_url(
        "http://127.0.0.1:8741/v1",
        "myapp",
        "abc123",
        depth=3,
        max_nodes=50,
    )
    assert url.endswith("/spaces/myapp/node/abc123/neighbors?depth=3&max_nodes=50")


def test_build_file_url_with_line_range() -> None:
    url = review_api.build_file_url(
        "http://127.0.0.1:8741/v1",
        "myapp",
        "scout/api/app.py",
        start_line=10,
        end_line=20,
    )
    assert "rel_path=scout%2Fapi%2Fapp.py" in url
    assert "start_line=10" in url
    assert "end_line=20" in url


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


def test_run_symbols_get() -> None:
    captured: dict[str, object] = {}

    def fake_http(method: str, url: str, body: dict | None, token: str) -> tuple[int, str]:
        captured["method"] = method
        captured["url"] = url
        return 0, "{}"

    with patch.object(review_api, "resolve_base_url", return_value="http://127.0.0.1:8741/v1"):
        with patch.object(review_api, "http_request", side_effect=fake_http):
            code = review_api.run(["symbols", "myapp", "scout/embed/"])
    assert code == 0
    assert captured["method"] == "GET"
    assert "symbols" in str(captured["url"])


def test_run_file_get() -> None:
    captured: dict[str, object] = {}

    def fake_http(method: str, url: str, body: dict | None, token: str) -> tuple[int, str]:
        captured["url"] = url
        return 0, "{}"

    with patch.object(review_api, "resolve_base_url", return_value="http://127.0.0.1:8741/v1"):
        with patch.object(review_api, "http_request", side_effect=fake_http):
            code = review_api.run(
                ["file", "myapp", "src/a.py", "--start-line", "1", "--end-line", "10"]
            )
    assert code == 0
    assert "/file?" in str(captured["url"])


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


def test_run_missing_base_url_exits_2() -> None:
    with patch.object(review_api, "resolve_base_url", return_value=None):
        assert review_api.run(["health"]) == 2


def test_parse_args_symbols() -> None:
    args = review_api.parse_args(["symbols", "space", "pkg/"])
    assert args.command == "symbols"
    assert args.path_prefix == "pkg/"


def test_parse_args_map() -> None:
    args = review_api.parse_args(["map", "space", "pkg/"])
    assert args.command == "map"
    assert args.path_prefix == "pkg/"


def test_run_map_same_as_symbols() -> None:
    symbols_url: str | None = None
    map_url: str | None = None

    def fake_http(method: str, url: str, body: dict | None, token: str) -> tuple[int, str]:
        return 0, "{}"

    def capture_symbols(method: str, url: str, body: dict | None, token: str) -> tuple[int, str]:
        nonlocal symbols_url
        symbols_url = url
        return 0, "{}"

    def capture_map(method: str, url: str, body: dict | None, token: str) -> tuple[int, str]:
        nonlocal map_url
        map_url = url
        return 0, "{}"

    with patch.object(review_api, "resolve_base_url", return_value="http://127.0.0.1:8741/v1"):
        with patch.object(review_api, "http_request", side_effect=capture_symbols):
            review_api.run(["symbols", "myapp", "scout/embed/"])
        with patch.object(review_api, "http_request", side_effect=capture_map):
            review_api.run(["map", "myapp", "scout/embed/"])

    assert symbols_url == map_url
    assert symbols_url is not None
    assert "/symbols?" in symbols_url
