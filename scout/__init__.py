"""Scout v2 — local code-graph + vector search for coding agents.

Metadata: v0.1.0 | Scout Contributors | 2026-06-12
"""

__version__ = "0.1.1"

try:
    import scout_core  # noqa: F401
except ImportError:  # pragma: no cover - dev without maturin build
    scout_core = None
