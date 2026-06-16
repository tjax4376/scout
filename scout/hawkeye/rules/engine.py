"""Hawkeye rule engine — evaluate rules against review context.

Metadata: v1.1.0 | Scout Contributors | 2026-06-15
Change rationale: Handler registry, ReviewContext docs, neighbor dedup tracking.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from scout.hawkeye.findings.schema import Finding, GraphEvidence
from scout.hawkeye.rules.antipatterns import match_antipatterns
from scout.hawkeye.rules.globs import path_matches, symbol_matches_regex

RuleHandler = Callable[[dict[str, Any], "ReviewContext", list[dict[str, Any]]], list[Finding]]


@dataclass
class ReviewContext:
    """Mutable state for one Hawkeye review pass."""

    session_id: str
    space: str
    changed_lines: dict[str, set[int]]
    symbols_by_prefix: dict[str, list[dict[str, Any]]]
    changed_symbols: list[dict[str, Any]]
    neighbors_by_node: dict[str, list[dict[str, Any]]]
    file_text: dict[str, str]
    neighbors_logged: set[str] = field(default_factory=set)
    stale: bool = False
    trace_step_seq: int | None = None


def _symbol_kind(sym: dict[str, Any]) -> str:
    return str(sym.get("kind") or "").lower()


def _symbol_path(sym: dict[str, Any]) -> str:
    return str(sym.get("rel_path") or "")


def _lines_overlap(sym: dict[str, Any], changed: set[int]) -> bool:
    if not changed:
        return False
    start = int(sym.get("start_line") or 0)
    end = int(sym.get("end_line") or start)
    return any(start <= line <= end for line in changed)


def _filter_symbols(symbols: list[dict[str, Any]], rule: dict[str, Any]) -> list[dict[str, Any]]:
    path_glob = str(rule.get("path_glob") or "**")
    kinds = {k.lower() for k in (rule.get("kinds") or [])}
    sym_regex = rule.get("symbol_regex")
    out: list[dict[str, Any]] = []
    for sym in symbols:
        rel = _symbol_path(sym)
        if not path_matches(path_glob, rel):
            continue
        if kinds and _symbol_kind(sym) not in kinds:
            continue
        if not symbol_matches_regex(sym_regex, str(sym.get("symbol") or "")):
            continue
        out.append(sym)
    return out


def _neighbor_paths(neighbors: list[dict[str, Any]], edge: str, direction: str) -> list[str]:
    paths: list[str] = []
    for nb in neighbors:
        if str(nb.get("edge") or "") != edge:
            continue
        rel = str(nb.get("rel_path") or "")
        if rel:
            paths.append(rel)
    return paths


def _evaluate_graph_neighbor(
    rule: dict[str, Any], ctx: ReviewContext, _antipatterns: list[dict[str, Any]]
) -> list[Finding]:
    findings: list[Finding] = []
    on = str(rule.get("on") or "any")
    edge = str(rule.get("edge") or "Calls")
    direction = str(rule.get("direction") or "incoming")
    min_count = int(rule.get("min_count") or 1)
    from_glob = rule.get("from_path_glob")
    to_excluded = list(rule.get("to_path_glob_excluded") or [])

    targets = ctx.changed_symbols if on == "changed_symbol" else []
    if not targets:
        all_syms: list[dict[str, Any]] = []
        for syms in ctx.symbols_by_prefix.values():
            all_syms.extend(syms)
        targets = _filter_symbols(all_syms, rule)

    for sym in targets:
        rel = _symbol_path(sym)
        changed = ctx.changed_lines.get(rel, set())
        if on == "changed_symbol" and changed and not _lines_overlap(sym, changed):
            continue
        node_id = str(sym.get("node_id") or "")
        neighbors = ctx.neighbors_by_node.get(node_id, [])
        paths = _neighbor_paths(neighbors, edge, direction)
        if from_glob:
            paths = [p for p in paths if path_matches(str(from_glob), p)]
        if to_excluded:
            paths = [
                p
                for p in paths
                if not any(path_matches(str(ex), p) for ex in to_excluded)
            ]
        if len(paths) < min_count:
            findings.append(
                Finding(
                    rule_id=str(rule["id"]),
                    severity=str(rule.get("severity") or "warning"),
                    message=str(rule.get("message") or rule.get("name") or rule["id"]),
                    rel_path=rel,
                    start_line=int(sym.get("start_line") or 1),
                    end_line=int(sym.get("end_line") or 1),
                    session_id=ctx.session_id,
                    scout=GraphEvidence(
                        node_id=node_id or None,
                        symbol=str(sym.get("symbol") or "") or None,
                        kind=_symbol_kind(sym) or None,
                        rel_path=rel,
                        start_line=int(sym.get("start_line") or 1),
                        end_line=int(sym.get("end_line") or 1),
                        identification_method=f"rule:{rule['id']}",
                        graph_evidence={
                            "edge": edge,
                            "direction": direction,
                            "matched_paths": paths,
                        },
                        trace_step_seq=ctx.trace_step_seq,
                    ),
                )
            )
            if node_id:
                ctx.neighbors_logged.add(node_id)
    return findings


def _evaluate_symbol_diff_overlap(
    rule: dict[str, Any], ctx: ReviewContext, _antipatterns: list[dict[str, Any]]
) -> list[Finding]:
    findings: list[Finding] = []
    require_neighbors = bool(rule.get("require_neighbors_logged"))
    require_overlap = bool(rule.get("require_symbol_overlap", True))
    path_glob = str(rule.get("path_glob") or "**")

    for rel, changed in ctx.changed_lines.items():
        if not path_matches(path_glob, rel):
            continue
        syms = [
            s
            for s in ctx.changed_symbols
            if _symbol_path(s) == rel and _lines_overlap(s, changed)
        ]
        if require_overlap and changed and not syms:
            findings.append(
                Finding(
                    rule_id=str(rule["id"]),
                    severity=str(rule.get("severity") or "warning"),
                    message=str(rule.get("message") or rule.get("name") or rule["id"]),
                    rel_path=rel,
                    session_id=ctx.session_id,
                    scout=GraphEvidence(
                        rel_path=rel,
                        identification_method=f"rule:{rule['id']}",
                    ),
                )
            )
        if require_neighbors:
            for sym in syms:
                node_id = str(sym.get("node_id") or "")
                if node_id and node_id not in ctx.neighbors_logged:
                    findings.append(
                        Finding(
                            rule_id=str(rule["id"]),
                            severity=str(rule.get("severity") or "warning"),
                            message=str(rule.get("message") or rule.get("name") or rule["id"]),
                            rel_path=rel,
                            start_line=int(sym.get("start_line") or 1),
                            end_line=int(sym.get("end_line") or 1),
                            session_id=ctx.session_id,
                            scout=GraphEvidence(
                                node_id=node_id,
                                symbol=str(sym.get("symbol") or "") or None,
                                rel_path=rel,
                                identification_method=f"rule:{rule['id']}",
                            ),
                        )
                    )
    return findings


def _evaluate_text_hunk(
    rule: dict[str, Any], ctx: ReviewContext, _antipatterns: list[dict[str, Any]]
) -> list[Finding]:
    findings: list[Finding] = []
    pattern = str(rule.get("pattern") or "").strip()
    if not pattern:
        return findings
    rx = re.compile(pattern)
    targets = _filter_symbols(ctx.changed_symbols, rule) if ctx.changed_symbols else []
    if not targets:
        for rel, text in ctx.file_text.items():
            if path_matches(str(rule.get("path_glob") or "**"), rel) and rx.search(text):
                findings.append(
                    Finding(
                        rule_id=str(rule["id"]),
                        severity=str(rule.get("severity") or "warning"),
                        message=str(rule.get("message") or rule["id"]),
                        rel_path=rel,
                        session_id=ctx.session_id,
                        scout=GraphEvidence(
                            rel_path=rel,
                            identification_method=f"rule:{rule['id']}",
                        ),
                    )
                )
        return findings

    for sym in targets:
        rel = _symbol_path(sym)
        text = ctx.file_text.get(rel, "")
        if text and rx.search(text):
            findings.append(
                Finding(
                    rule_id=str(rule["id"]),
                    severity=str(rule.get("severity") or "warning"),
                    message=str(rule.get("message") or rule["id"]),
                    rel_path=rel,
                    start_line=int(sym.get("start_line") or 1),
                    end_line=int(sym.get("end_line") or 1),
                    session_id=ctx.session_id,
                    scout=GraphEvidence(
                        node_id=str(sym.get("node_id") or "") or None,
                        symbol=str(sym.get("symbol") or "") or None,
                        rel_path=rel,
                        identification_method=f"rule:{rule['id']}",
                    ),
                )
            )
    return findings


def _evaluate_staleness_gate(
    rule: dict[str, Any], ctx: ReviewContext, _antipatterns: list[dict[str, Any]]
) -> list[Finding]:
    if not ctx.stale:
        return []
    path_glob = str(rule.get("path_glob") or "**")
    for rel in ctx.changed_lines:
        if path_matches(path_glob, rel):
            return [
                Finding(
                    rule_id=str(rule["id"]),
                    severity=str(rule.get("severity") or "error"),
                    message=str(rule.get("message") or rule["id"]),
                    rel_path=rel,
                    session_id=ctx.session_id,
                    scout=GraphEvidence(
                        rel_path=rel,
                        identification_method=f"rule:{rule['id']}",
                        graph_evidence={"stale": True},
                    ),
                )
            ]
    return []


def _evaluate_anti_pattern_ref(
    rule: dict[str, Any], ctx: ReviewContext, antipatterns: list[dict[str, Any]]
) -> list[Finding]:
    aid = str(rule.get("anti_pattern_id") or "")
    selected = [ap for ap in antipatterns if str(ap.get("id")) == aid]
    if not selected:
        return []
    findings: list[Finding] = []
    path_glob = str(rule.get("path_glob") or "**")
    for rel in ctx.changed_lines:
        if not path_matches(path_glob, rel):
            continue
        text = ctx.file_text.get(rel, "")
        neighbors: list[dict[str, Any]] = []
        for sym in ctx.changed_symbols:
            if _symbol_path(sym) == rel:
                node_id = str(sym.get("node_id") or "")
                neighbors.extend(ctx.neighbors_by_node.get(node_id, []))
        findings.extend(
            match_antipatterns(
                selected,
                rel_path=rel,
                text=text,
                neighbors=neighbors,
                session_id=ctx.session_id,
            )
        )
    return findings


def _evaluate_path_glob(
    rule: dict[str, Any], ctx: ReviewContext, _antipatterns: list[dict[str, Any]]
) -> list[Finding]:
    findings: list[Finding] = []
    path_glob = str(rule.get("path_glob") or "")
    for rel in ctx.changed_lines:
        if path_matches(path_glob, rel):
            findings.append(
                Finding(
                    rule_id=str(rule["id"]),
                    severity=str(rule.get("severity") or "warning"),
                    message=str(rule.get("message") or rule["id"]),
                    rel_path=rel,
                    session_id=ctx.session_id,
                )
            )
    return findings


RULE_HANDLERS: dict[str, RuleHandler] = {
    "graph_neighbor": _evaluate_graph_neighbor,
    "symbol_diff_overlap": _evaluate_symbol_diff_overlap,
    "text_hunk": _evaluate_text_hunk,
    "staleness_gate": _evaluate_staleness_gate,
    "anti_pattern_ref": _evaluate_anti_pattern_ref,
    "path_glob": _evaluate_path_glob,
}


def evaluate_rules(
    rules: list[dict[str, Any]],
    antipatterns: list[dict[str, Any]],
    ctx: ReviewContext,
) -> list[Finding]:
    findings: list[Finding] = []
    for rule in rules:
        if rule.get("enabled", True) is False:
            continue
        rtype = str(rule.get("type") or "")
        if not rtype:
            raise ValueError(f"rule {rule.get('id')} missing type")
        handler = RULE_HANDLERS.get(rtype)
        if handler is None:
            raise ValueError(f"unknown rule type: {rtype}")
        findings.extend(handler(rule, ctx, antipatterns))
    return findings
