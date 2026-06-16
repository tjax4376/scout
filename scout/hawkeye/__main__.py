"""CLI entry: python -m scout.hawkeye

Metadata: v1.1.0 | Scout Contributors | 2026-06-15
Change rationale: Exit code semantics, cached config, help strings, docstrings.
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
from pathlib import Path

from scout.hawkeye.config import HawkeyeConfig, load_config, load_config_or_defaults, user_config_dir
from scout.hawkeye.discovery import prepare_setup
from scout.hawkeye.findings.sarif import write_sarif
from scout.hawkeye.hybrid.escalate import build_escalation_bundle, write_escalation
from scout.hawkeye.learning.miner import mine_traces, write_candidates
from scout.hawkeye.learning.promote import promote_candidate
from scout.hawkeye.runner.playbook import run_review
from scout.hawkeye.runner.path_scope import directory_scope, file_scope
from scout.hawkeye.runner.replay import print_replay_report, replay_session
from scout.hawkeye.setup_cmd import run_setup
from scout.hawkeye.trace.store import TraceStore

EXIT_SUCCESS = 0
EXIT_FINDINGS = 1
EXIT_RUNTIME = 2


def _safe_int(value: object, default: int = 1) -> int:
    if value is None:
        return default
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _project_root(path: Path | None) -> Path:
    return path or Path.cwd()


@functools.lru_cache(maxsize=16)
def _cached_load_config(
    project_root_str: str,
    use_project: bool,
    rules_path: str | None,
    antipatterns_path: str | None,
    allow_defaults: bool,
) -> HawkeyeConfig:
    root = Path(project_root_str)
    project_root = root if use_project or (root / ".hawkeye").is_dir() else None
    rules_file = Path(rules_path) if rules_path else None
    antipatterns_file = Path(antipatterns_path) if antipatterns_path else None
    if allow_defaults:
        return load_config_or_defaults(
            project_root or root,
            rules_file=rules_file,
            antipatterns_file=antipatterns_file,
        )
    return load_config(
        project_root,
        rules_file=rules_file,
        antipatterns_file=antipatterns_file,
    )


def _load_cfg(args: argparse.Namespace, *, allow_defaults: bool = False) -> tuple[HawkeyeConfig, Path]:
    root = _project_root(getattr(args, "project_root", None))
    use_project = bool(getattr(args, "project", False))
    rules = getattr(args, "rules", None)
    antipatterns = getattr(args, "antipatterns", None)
    cfg = _cached_load_config(
        str(root.resolve()),
        use_project,
        str(rules) if rules else None,
        str(antipatterns) if antipatterns else None,
        allow_defaults,
    )
    return cfg, root


def _runtime_error(exc: BaseException) -> int:
    print(str(exc), file=sys.stderr)
    return EXIT_RUNTIME


def cmd_setup(args: argparse.Namespace) -> int:
    """Initialize Hawkeye config, rules, and antipatterns on disk."""
    try:
        root = _project_root(args.project_root)
        api_url, space = prepare_setup(
            scout_api=args.scout_api,
            space=args.space,
            project=args.project,
            project_root=root,
            yes=args.yes,
        )
        dest = run_setup(
            scout_api=api_url,
            space=space,
            project=args.project,
            project_root=root,
            rules_file=args.rules_file,
            antipatterns_file=args.antipatterns_file,
            force=args.force,
        )
    except (FileExistsError, OSError, ValueError) as exc:
        return _runtime_error(exc)
    print(f"hawkeye configured: {dest}")
    return EXIT_SUCCESS


def _review_scope(args: argparse.Namespace, root: Path) -> tuple[str | None, object | None]:
    """Return (diff_ref, prebuilt_scope) for review."""
    if args.path and args.file:
        raise ValueError("use only one of --diff, --path, or --file")
    if args.path:
        return None, directory_scope(root, Path(args.path))
    if args.file:
        return None, file_scope(root, Path(args.file))
    if args.diff is not None:
        return args.diff, None
    return "HEAD~1", None


def cmd_review(args: argparse.Namespace) -> int:
    """Run deterministic review on git diff, file, or directory scope."""
    backend_mode = getattr(args, "backend", "auto") or "auto"
    allow_defaults = backend_mode in ("auto", "filesystem")
    try:
        cfg, root = _load_cfg(args, allow_defaults=allow_defaults)
        diff_ref, scope = _review_scope(args, root)
        result = run_review(
            cfg,
            diff_ref=diff_ref or "HEAD~1",
            scope=scope,
            repo_root=root,
            space=args.space,
            backend_mode=backend_mode,
            project=args.project,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return _runtime_error(exc)

    print(f"session: {result.session_id}")
    print(f"backend: {result.backend}")
    print(f"findings: {len(result.findings)} (hash {result.findings_hash})")
    print(f"trace: {result.trace_path}")
    for finding in result.findings:
        print(f"  [{finding.severity}] {finding.rule_id}: {finding.message} ({finding.rel_path})")

    if args.sarif:
        write_sarif(args.sarif, result.findings)
        print(f"sarif: {args.sarif}")

    if args.hybrid:
        try:
            trace = TraceStore.load(cfg.trace_dir, result.session_id)
        except FileNotFoundError as exc:
            return _runtime_error(exc)
        bundle = build_escalation_bundle(
            session_id=result.session_id,
            scope=result.scope,
            findings=result.findings,
            trace=trace,
        )
        out = args.escalation_out or (cfg.config_dir / "traces" / f"{result.session_id}-escalation.json")
        write_escalation(out, bundle)
        print(f"escalation: {out}")
        if bundle.get("unmapped_hunks"):
            print("Hybrid: unmapped hunks present — hand off escalation.json to agent (no LLM call in v1).")

    has_errors = any(f.severity == "error" for f in result.findings)
    if args.advisory:
        return EXIT_FINDINGS if has_errors else EXIT_SUCCESS
    return EXIT_FINDINGS if has_errors else EXIT_SUCCESS


def cmd_replay(args: argparse.Namespace) -> int:
    """Replay a stored review session and compare findings hash."""
    try:
        cfg, root = _load_cfg(args)
        report = replay_session(cfg, args.session, repo_root=root, dry_run=args.dry_run)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return _runtime_error(exc)
    print(print_replay_report(report))
    if not args.dry_run and report.match is False:
        return EXIT_FINDINGS
    return EXIT_SUCCESS


def cmd_mine(args: argparse.Namespace) -> int:
    """Mine trace files for recurring finding patterns."""
    try:
        cfg, _ = _load_cfg(args)
        report = mine_traces(
            cfg.trace_dir,
            threshold=args.threshold,
            limit=args.limit,
            offset=args.offset,
            batch_size=args.batch_size,
        )
        out = args.output or (cfg.config_dir / "candidate-rules.yaml")
        write_candidates(out, report)
    except (FileNotFoundError, ValueError) as exc:
        return _runtime_error(exc)
    print(f"candidates: {len(report.get('candidates') or [])} -> {out}")
    return EXIT_SUCCESS


def cmd_promote(args: argparse.Namespace) -> int:
    """Approve or reject a mined rule candidate."""
    try:
        cfg, _ = _load_cfg(args)
        candidates = args.candidates or (cfg.config_dir / "candidate-rules.yaml")
        if args.approve:
            promote_candidate(cfg.config_dir / "rules.yaml", candidates, args.candidate_id, approve=True)
        elif args.reject:
            promote_candidate(cfg.config_dir / "rules.yaml", candidates, args.candidate_id, approve=False)
        else:
            raise ValueError("specify --approve or --reject")
    except (FileNotFoundError, ValueError) as exc:
        return _runtime_error(exc)
    print(f"candidate {args.candidate_id}: {'promoted' if args.approve else 'rejected'}")
    return EXIT_SUCCESS


def cmd_feedback(args: argparse.Namespace) -> int:
    """Append human feedback for a finding to the session trace."""
    try:
        cfg, _ = _load_cfg(args)
        trace = TraceStore.load(cfg.trace_dir, args.session)
        trace.record_feedback(args.finding, args.verdict)
    except FileNotFoundError as exc:
        return _runtime_error(exc)
    except ValueError as exc:
        return _runtime_error(exc)
    print(f"feedback recorded: {args.finding} -> {args.verdict}")
    return EXIT_SUCCESS


def cmd_export_sarif(args: argparse.Namespace) -> int:
    """Export findings from a stored session trace as SARIF."""
    findings = []
    try:
        cfg, _ = _load_cfg(args)
        trace = TraceStore.load(cfg.trace_dir, args.session)
        from scout.hawkeye.findings.schema import Finding, GraphEvidence

        for record in trace.iter_records():
            if record.get("type") != "finding":
                continue
            raw = record.get("finding") or {}
            scout_raw = raw.get("scout") or {}
            hawkeye_raw = raw.get("hawkeye") or {}
            raw_seq = scout_raw.get("trace_step_seq")
            trace_step_seq = None if raw_seq is None else _safe_int(raw_seq, 0) or None
            scout = GraphEvidence(
                node_id=scout_raw.get("node_id"),
                symbol=scout_raw.get("symbol"),
                kind=scout_raw.get("kind"),
                rel_path=scout_raw.get("rel_path"),
                start_line=_safe_int(scout_raw.get("start_line"), 1),
                end_line=_safe_int(scout_raw.get("end_line"), 1),
                identification_method=str(scout_raw.get("identification_method") or ""),
                graph_evidence=dict(scout_raw.get("graph_evidence") or {}),
                trace_step_seq=trace_step_seq,
            )
            start_line = _safe_int(raw.get("start_line"), 1)
            end_line = _safe_int(raw.get("end_line"), start_line)
            findings.append(
                Finding(
                    finding_id=str(raw.get("finding_id") or ""),
                    rule_id=str(raw.get("rule_id") or ""),
                    severity=str(raw.get("severity") or "warning"),
                    message=str(raw.get("message") or ""),
                    rel_path=str(raw.get("rel_path") or ""),
                    start_line=start_line,
                    end_line=end_line,
                    scout=scout,
                    session_id=str(hawkeye_raw.get("session_id") or args.session),
                    mapped=bool(hawkeye_raw.get("mapped", True)),
                    escalate=bool(hawkeye_raw.get("escalate", False)),
                )
            )
        write_sarif(args.output, findings)
    except FileNotFoundError as exc:
        return _runtime_error(exc)
    except ValueError as exc:
        return _runtime_error(exc)
    print(f"sarif: {args.output} ({len(findings)} results)")
    return EXIT_SUCCESS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hawkeye — local graph-aware code reviewer")
    sub = parser.add_subparsers(dest="command", required=True)

    setup_p = sub.add_parser("setup", help="Initialize Hawkeye config and rule pack")
    setup_p.add_argument(
        "--scout-api",
        default=None,
        help="Scout API base URL (default: discover running scout serve on 8741-8799)",
    )
    setup_p.add_argument(
        "--space",
        default=None,
        help="Scout space name (default: list from Scout API or prompt)",
    )
    setup_p.add_argument("--project", action="store_true")
    setup_p.add_argument("--project-root", type=Path, default=Path.cwd())
    setup_p.add_argument("--rules-file", type=Path, default=None)
    setup_p.add_argument("--antipatterns-file", type=Path, default=None)
    setup_p.add_argument("--force", action="store_true")
    setup_p.add_argument("--yes", action="store_true", help="Skip setup confirmation prompts")

    review_p = sub.add_parser("review", help="Run deterministic code review")
    review_p.add_argument(
        "--diff",
        default=None,
        help="Git diff ref to review (default: HEAD~1 when no --path/--file)",
    )
    review_p.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Review all eligible files under this directory",
    )
    review_p.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Review a single file",
    )
    review_p.add_argument(
        "--backend",
        choices=["auto", "graph", "filesystem"],
        default="auto",
        help="Review data source: Scout graph (graph), local disk (filesystem), or auto-detect",
    )
    review_p.add_argument("--space", default=None)
    review_p.add_argument("--project", action="store_true")
    review_p.add_argument("--project-root", type=Path, default=Path.cwd())
    review_p.add_argument(
        "--rules",
        type=Path,
        default=None,
        help="Optional YAML overlay merged onto configured rules",
    )
    review_p.add_argument(
        "--antipatterns",
        type=Path,
        default=None,
        help="Optional YAML overlay merged onto configured antipatterns",
    )
    review_p.add_argument("--sarif", type=Path, default=None)
    review_p.add_argument("--hybrid", action="store_true")
    review_p.add_argument("--escalation-out", type=Path, default=None)
    review_p.add_argument("--advisory", action="store_true", help="Exit 0 unless error severity")

    replay_p = sub.add_parser("replay", help="Replay stored review session")
    replay_p.add_argument("--session", required=True)
    replay_p.add_argument("--dry-run", action="store_true")
    replay_p.add_argument("--project", action="store_true")
    replay_p.add_argument("--project-root", type=Path, default=Path.cwd())
    replay_p.add_argument(
        "--rules",
        type=Path,
        default=None,
        help="Optional YAML overlay merged onto configured rules",
    )
    replay_p.add_argument(
        "--antipatterns",
        type=Path,
        default=None,
        help="Optional YAML overlay merged onto configured antipatterns",
    )

    mine_p = sub.add_parser("mine", help="Mine traces for rule candidates")
    mine_p.add_argument("--threshold", type=int, default=3)
    mine_p.add_argument("--output", type=Path, default=None)
    mine_p.add_argument("--limit", type=int, default=None, help="Max trace files to scan")
    mine_p.add_argument("--offset", type=int, default=0, help="Skip first N trace files")
    mine_p.add_argument("--batch-size", type=int, default=None, help="Max finding records to process")
    mine_p.add_argument("--project", action="store_true")
    mine_p.add_argument("--project-root", type=Path, default=Path.cwd())

    promote_p = sub.add_parser("promote", help="Approve or reject mined rule candidate")
    promote_p.add_argument("--candidate-id", required=True)
    promote_p.add_argument("--candidates", type=Path, default=None)
    promote_p.add_argument("--approve", action="store_true")
    promote_p.add_argument("--reject", action="store_true")
    promote_p.add_argument("--project", action="store_true")
    promote_p.add_argument("--project-root", type=Path, default=Path.cwd())

    feedback_p = sub.add_parser("feedback", help="Record human feedback on a finding")
    feedback_p.add_argument("--session", required=True)
    feedback_p.add_argument("--finding", required=True, help="finding_id")
    feedback_p.add_argument("--verdict", required=True, choices=["accepted", "rejected"])
    feedback_p.add_argument("--project", action="store_true")
    feedback_p.add_argument("--project-root", type=Path, default=Path.cwd())

    export_p = sub.add_parser("export-sarif", help="Export session findings as SARIF")
    export_p.add_argument("--session", required=True)
    export_p.add_argument("--output", type=Path, required=True)
    export_p.add_argument("--project", action="store_true")
    export_p.add_argument("--project-root", type=Path, default=Path.cwd())

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "setup": cmd_setup,
        "review": cmd_review,
        "replay": cmd_replay,
        "mine": cmd_mine,
        "promote": cmd_promote,
        "feedback": cmd_feedback,
        "export-sarif": cmd_export_sarif,
    }
    handler = handlers.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return EXIT_RUNTIME
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
