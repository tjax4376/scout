"""Anti-pattern matching for Hawkeye.

Metadata: v1.0.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import re
from typing import Any

from scout.hawkeye.findings.schema import Finding, GraphEvidence
from scout.hawkeye.rules.globs import path_matches


def match_antipatterns(
    antipatterns: list[dict[str, Any]],
    *,
    rel_path: str,
    text: str,
    neighbors: list[dict[str, Any]],
    session_id: str,
) -> list[Finding]:
    findings: list[Finding] = []
    for ap in antipatterns:
        ap_type = str(ap.get("type") or "")
        path_glob = str(ap.get("path_glob") or "**")
        if not path_matches(path_glob, rel_path):
            continue
        msg = str(ap.get("message") or ap.get("description") or ap.get("id"))
        severity = str(ap.get("severity") or "warning")
        aid = str(ap["id"])

        if ap_type == "text_regex":
            pattern = str(ap.get("pattern") or "").strip()
            if pattern and re.search(pattern, text):
                findings.append(
                    Finding(
                        rule_id=aid,
                        severity=severity,
                        message=msg,
                        rel_path=rel_path,
                        session_id=session_id,
                        scout=GraphEvidence(
                            rel_path=rel_path,
                            identification_method=f"antipattern:{aid}",
                        ),
                    )
                )
        elif ap_type == "import_edge":
            from_glob = str(ap.get("from_path_glob") or "**")
            to_glob = str(ap.get("to_path_glob") or "**")
            if not path_matches(from_glob, rel_path):
                continue
            for nb in neighbors:
                if str(nb.get("edge") or "") != "Imports":
                    continue
                target_path = str(nb.get("rel_path") or "")
                if path_matches(to_glob, target_path):
                    findings.append(
                        Finding(
                            rule_id=aid,
                            severity=severity,
                            message=msg,
                            rel_path=rel_path,
                            session_id=session_id,
                            scout=GraphEvidence(
                                rel_path=rel_path,
                                identification_method=f"antipattern:{aid}",
                                graph_evidence={"import_target": target_path},
                            ),
                        )
                    )
    return findings
