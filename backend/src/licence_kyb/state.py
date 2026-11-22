"""The state carried through one run of the graph.

Each node reads only what it needs and returns a partial update. Large or personal payloads
(page images, file bytes) stay out of the state; they are referenced by path or run ID.
"""

from __future__ import annotations

from typing import Any, TypedDict


class RunState(TypedDict, total=False):
    run_id: str
    applicant_name: str
    status: str
    # intake / preprocess
    file: dict[str, Any]
    pages: dict[str, Any]
    # route / extract / validate / resolve
    route: dict[str, Any]
    extraction: dict[str, Any]
    secondary: dict[str, Any]
    agreement: dict[str, bool]
    serving_models: list[str]
    rule_results: list[dict[str, Any]]
    proposals: list[dict[str, Any]]
    resolver_rounds: int
    # confidence / gate / form
    confidence: dict[str, dict[str, Any]]
    decision: dict[str, Any]
    form: dict[str, Any]
    # review / submit
    pending_decisions: dict[str, Any]
    submission: dict[str, Any]
    reasons: list[dict[str, Any]]
