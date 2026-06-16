"""SARIF 2.1.0 emitter with Scout graph evidence extensions.

Metadata: v1.1.0 | Scout Contributors | 2026-06-15
Change rationale: Explicit with-open write path for safe I/O.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scout.hawkeye.findings.schema import SEVERITY_TO_SARIF, Finding


def findings_to_sarif(findings: list[Finding], *, tool_name: str = "hawkeye") -> dict[str, Any]:
    rules_index: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for finding in findings:
        if finding.rule_id not in rules_index:
            rules_index[finding.rule_id] = {
                "id": finding.rule_id,
                "name": finding.rule_id,
                "shortDescription": {"text": finding.message[:120]},
            }
        result: dict[str, Any] = {
            "ruleId": finding.rule_id,
            "level": SEVERITY_TO_SARIF.get(finding.severity, "warning"),
            "message": {"text": finding.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": finding.rel_path},
                        "region": {
                            "startLine": finding.start_line,
                            "endLine": finding.end_line,
                        },
                    }
                }
            ],
            "properties": {},
        }
        props = result["properties"]
        if finding.scout:
            props["scout"] = finding.scout.to_dict()
        props["hawkeye"] = {
            "session_id": finding.session_id,
            "finding_id": finding.finding_id,
            "mapped": finding.mapped,
            "escalate": finding.escalate,
        }
        results.append(result)

    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": tool_name,
                        "informationUri": "https://github.com/tjax4376/scout",
                        "rules": list(rules_index.values()),
                    }
                },
                "results": results,
            }
        ],
    }


def write_sarif(path: Path, findings: list[Finding]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(findings_to_sarif(findings), indent=2) + "\n")
