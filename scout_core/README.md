# scout_core

Rust engine for Scout v2: workspace scan, tree-sitter parse, petgraph code graph, sqlite-vec embeddings store, vector search with neighbor traversal.

## Role

Python shell (`scout/`) calls this crate via **pyo3** bindings in `src/pyapi.rs`. No HTTP, no embed calls — Rust handles structure and search only.

## Modules

| File | Purpose |
|------|---------|
| `scan.rs` | Walk workspace, apply skip globs, detect language |
| `parse/` | tree-sitter parsers (Python, JS/TS, Rust, Go) |
| `graph.rs` | Build petgraph: `contains`, `imports`, `calls` edges |
| `chunk.rs` | Symbol-level text chunks for embedding |
| `index.rs` | Write/read `index.db` (sqlite-vec) + `graph.bin` |
| `search.rs` | Vector search + neighbor BFS (anchor pivot) |
| `staleness.rs` | Compare manifest vs workspace mtime/hash |
| `pyapi.rs` | Exported Python functions |

## Build

```bash
# From repo root (requires maturin in venv)
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin develop --release
python -c "import scout_core; print(scout_core.py_core_version())"
```

## Tests

```bash
cargo test -p scout_core
```

Integration tests that exercise pyo3 live in `tests/integration/test_indexing.py` (pytest, requires maturin build).

## Dependencies

See inline comments in `Cargo.toml`. Key runtime deps: petgraph, rusqlite + sqlite-vec, tree-sitter grammars, pyo3.

## Specs

- `openspec/changes/scout-simple-mvp1/specs/code-indexing/spec.md`
- `openspec/changes/scout-simple-mvp1/specs/vector-search/spec.md`
