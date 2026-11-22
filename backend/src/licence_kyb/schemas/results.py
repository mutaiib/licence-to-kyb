"""Rule results, reason codes, routing decisions and resolver proposals (data-model.md)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from licence_kyb.schemas.licence import StrictModel

ReasonCode = Literal[
    # file
    "invalid_type",
    "too_large",
    "too_many_pages",
    "image_too_large",
    "unreadable_file",
    # document
    "out_of_scope",
    "unclear_document",
    "unknown_authority",
    # expiry
    "expired",
    "expiry_uncertain",
    "near_expiry",
    # values
    "number_format",
    "date_order",
    "shares_total",
    "sole_owner_count",
    "legal_form_not_allowed",
    "arabic_name_missing",
    "high_risk_activity",
    "evidence_mismatch",
    "qr_mismatch",
    "registry_not_found",
    "registry_expiry_mismatch",
    "registry_unavailable",
    "applicant_name_mismatch",
    "owners_unclear",
    "ubo_needs_examination",
    "low_confidence",
    # process
    "processing_failed",
    "budget_exhausted",
    "fallback_model",
    "resolver_budget",
    "verification_failed",
    "reviewer_rejected",
    # escape
    "other",
]

FILE_REASONS: frozenset[str] = frozenset(
    {"invalid_type", "too_large", "too_many_pages", "image_too_large", "unreadable_file"}
)

ErrorCode = Literal[
    "invalid_credentials",
    "session_expired",
    "forbidden",
    "blocking_rule_failed",
    "not_overridable",
    "undecided_fields",
    "stale_version",
    "reason_required",
    "not_approved",
    "not_awaiting_submit",
    "not_rejected",
    "not_retryable",
    "invalid_type",
    "too_large",
    "too_many_pages",
    "image_too_large",
    "rate_limited",
]

Severity = Literal["block", "warn"]
Outcome = Literal["passed", "failed", "could_not_run", "not_applicable"]
Route = Literal["ready", "needs_review", "reject"]


class RuleResult(StrictModel):
    rule_id: str
    fields: tuple[str, ...] = ()
    severity: Severity
    outcome: Outcome
    reason_code: ReasonCode | None = None
    overridable: bool = False
    detail: dict[str, str] = Field(default_factory=dict)
    """Values for the UI string, e.g. ``{"days": "10"}``. Never asserted as text."""

    @property
    def counts_as_failed(self) -> bool:
        return self.outcome in ("failed", "could_not_run")


class Reason(StrictModel):
    code: ReasonCode
    field: str | None = None
    rule_id: str | None = None


class Decision(StrictModel):
    route: Route
    reasons: tuple[Reason, ...] = ()


class ProposedFix(StrictModel):
    field: str
    new_value: str
    evidence_quote: str
    self_confidence: Literal["high", "medium", "low", "unknown"]
    rationale: str = Field(max_length=300)
    accepted: bool = False


class FieldConfidence(StrictModel):
    score: float = Field(ge=0, le=1)
    signals: dict[str, float]
    threshold: float = Field(ge=0, le=1)
