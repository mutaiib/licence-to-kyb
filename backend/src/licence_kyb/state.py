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
    # proposals and resolver_rounds: used from User Story 4 (the resolver).
    proposals: list[dict[str, Any]]
    resolver_rounds: int
    # confidence / gate / form
    # Used from User Story 3 (confidence and routing).
    confidence: dict[str, dict[str, Any]]
    decision: dict[str, Any]
    form: dict[str, Any]
    # review / submit
    action: dict[str, Any]
    """The reviewer action the run resumed with (``wait_for_reviewer``)."""
    decisions: dict[str, Any]
    """Every field decision so far, keyed by form field (or rule ID for an override)."""
    read_extraction: dict[str, Any]
    """The extraction as the model read it, before any correction."""
    applied_ids: list[str]
    """Decision and action IDs already applied; a repeated ID changes nothing."""
    submission: dict[str, Any]
    reasons: list[dict[str, Any]]
