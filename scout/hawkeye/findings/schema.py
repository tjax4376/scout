"""Internal finding model for Hawkeye.

Metadata: v1.0.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any


SEVERITY_TO_SARIF = {
    "error": "error",
    "warning": "warning",
    "note": "note",
    "info": "note",
}


@dataclass
class GraphEvidence:
    node_id: str | None = None
    symbol: str | None = None
    kind: str | None = None
    rel_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    identification_method: str = ""
    graph_evidence: dict[str, Any] = field(default_factory=dict)
    trace_step_seq: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.node_id:
            out["node_id"] = self.node_id
        if self.symbol:
            out["symbol"] = self.symbol
        if self.kind:
            out["kind"] = self.kind
        if self.rel_path:
            out["rel_path"] = self.rel_path
        if self.start_line is not None:
            out["start_line"] = self.start_line
        if self.end_line is not None:
            out["end_line"] = self.end_line
        if self.identification_method:
            out["identification_method"] = self.identification_method
        if self.graph_evidence:
            out["graph_evidence"] = self.graph_evidence
        if self.trace_step_seq is not None:
            out["trace_step_seq"] = self.trace_step_seq
        return out


@dataclass
class Finding:
    rule_id: str
    severity: str
    message: str
    rel_path: str
    start_line: int = 1
    end_line: int = 1
    scout: GraphEvidence | None = None
    session_id: str = ""
    mapped: bool = True
    escalate: bool = False
    finding_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "rel_path": self.rel_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "scout": self.scout.to_dict() if self.scout else {},
            "hawkeye": {
                "session_id": self.session_id,
                "mapped": self.mapped,
                "escalate": self.escalate,
            },
        }


def findings_hash(findings: list[Finding]) -> str:
    payload = [
        {
            "rule_id": f.rule_id,
            "severity": f.severity,
            "message": f.message,
            "rel_path": f.rel_path,
            "start_line": f.start_line,
            "end_line": f.end_line,
        }
        for f in sorted(findings, key=lambda x: (x.rule_id, x.rel_path, x.start_line))
    ]
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]
