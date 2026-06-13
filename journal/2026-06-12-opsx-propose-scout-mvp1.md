# Journal: OpenSpec Proposal — Scout Simple MVP1

**Date:** 2026-06-12
**Author:** Cursor Agent
**Version:** 1.0

## Context

User ran `/opsx-propose` with `scope/scout-simple-mvp1.md` — grill-closed scope for Scout v2 Simple MVP1. 35 decisions resolved. Goal: generate full OpenSpec change artifacts (proposal, design, specs, tasks) ready for `/opsx:apply` implementation.

## Discussion Points

- Derived change name `scout-simple-mvp1` from scope doc
- Split capabilities into 8 spec modules aligned with project modularity principles:
  - `code-indexing`, `vector-search`, `rest-api`, `cli-and-serve`, `embed-providers`, `prescan`, `space-config`, `agent-skill`
- No existing specs in `openspec/specs/` — all new capabilities, no deltas
- Design captures Rust/Python pyo3 split, sqlite-vec + petgraph data layer, anchor-pivot neighbor traversal, sync reindex, local-first embed providers
- Tasks ordered by dependency: scaffold → config → scan/parse/graph/index → embed/prescan → search/neighbors → bindings → CLI/API → skill → CI → integration tests

## Code Changed

No application code — OpenSpec artifacts only:

| Artifact | Path | Description |
|----------|------|-------------|
| proposal.md | `openspec/changes/scout-simple-mvp1/proposal.md` | Why, what changes, 8 capabilities, impact |
| design.md | `openspec/changes/scout-simple-mvp1/design.md` | Architecture, 11 decisions, risks, module layout |
| specs (×8) | `openspec/changes/scout-simple-mvp1/specs/*/spec.md` | Normative requirements + scenarios per capability |
| tasks.md | `openspec/changes/scout-simple-mvp1/tasks.md` | 17 task groups, 72 checkboxes |

## Summary

All apply-ready artifacts created. Change at `openspec/changes/scout-simple-mvp1/`. Ready for `/opsx:apply`.
