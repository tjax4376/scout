"""Ask Scout — graph structure Q&A without embed/LLM.

Metadata: v0.1.0 | Scout Contributors | 2026-07-14
Change rationale: ask-scout-structure — compact structure answers to save agent prompt tokens.
"""

from __future__ import annotations

from scout.ask.models import AskStructureRequest, AskStructureResponse
from scout.ask.structure import AskGraphMissingError, ask_structure

__all__ = [
    "AskGraphMissingError",
    "AskStructureRequest",
    "AskStructureResponse",
    "ask_structure",
]
