"""API bodies (contracts/http-api.md). The OpenAPI schema and the frontend types come from here."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from licence_kyb.schemas.kyb_form import FieldState, FormValue
from licence_kyb.schemas.licence import Origin, Status
from licence_kyb.schemas.results import ActionErrorCode, Outcome, ReasonCode, Route, Severity

RunStatus = Literal[
    "received", "processing", "rejected", "awaiting_review", "awaiting_submit", "submitted", "done"
]


class SessionIn(BaseModel):
    username: str
    password: str


class SessionOut(BaseModel):
    reviewer: str


class ErrorOut(BaseModel):
    code: str


class RunCreated(BaseModel):
    run_id: str
    status: RunStatus
    duplicate: bool = False


class UploadRejected(BaseModel):
    reason_code: ReasonCode
    run_id: str | None


class ReasonView(BaseModel):
    code: ReasonCode
    field: str | None = None
    rule_id: str | None = None
    detail: dict[str, str] = {}
    """Values for the reason's UI string, e.g. ``{"days": "10"}``."""


StepState = Literal["done", "running", "pending", "skipped"]


class StepView(BaseModel):
    name: str
    state: StepState
    duration_ms: int | None = None


class EvidenceBox(BaseModel):
    page: int
    x: float
    y: float
    w: float
    h: float


class RuleView(BaseModel):
    rule_id: str
    severity: Severity
    outcome: Outcome
    reason_code: ReasonCode | None
    overridable: bool
    detail: dict[str, str] = {}


# Used from User Story 3 (confidence and routing).
class ConfidenceView(BaseModel):
    """How sure the system is of a read value, from its evidence (FR-019)."""

    score: float
    threshold: float | None
    """None for a field that is scored but never flagged for low confidence."""
    signals: dict[str, float]


class FormFieldView(BaseModel):
    value: FormValue
    """The form value. A field without one shows the value as read from the document."""
    state: FieldState
    status: Status
    """Whether the document shows the field, does not show it, or shows it unreadably."""
    origin: Origin = "read"
    evidence_quote: str | None = None
    evidence_box: EvidenceBox | None = None
    confidence: ConfidenceView | None = None
    rule_results: list[RuleView] = []
    model_rationale: str | None = None
    """The resolver's explanation for its latest proposal on this field: model output (US4)."""
    proposal_accepted: bool | None = None
    """Whether that proposal replaced the value. None when there was no proposal."""


class FormView(BaseModel):
    version: int
    fields: dict[str, FormFieldView]


class RunView(BaseModel):
    run_id: str
    status: RunStatus
    steps: list[StepView]
    route: Route | None
    reasons: list[ReasonView]
    form: FormView | None
    required_documents: list[str]
    pages: int


class RunSummary(BaseModel):
    run_id: str
    created_at: str
    applicant_name: str
    route: Route | None
    status: RunStatus
    cost_usd: float
    duration_ms: int


class RunList(BaseModel):
    runs: list[RunSummary]


# ------------------------------------------------------------------ reviewer actions (US2)
ActionId = Annotated[str, Field(min_length=1, max_length=64)]
"""A client-made ID. Sending the same ID again changes nothing (idempotency)."""
Reason = Annotated[str, Field(min_length=1, max_length=500)]


class DecisionIn(BaseModel):
    """One decision on one field (``approve`` or ``correct``) or on one check (``override``)."""

    decision_id: ActionId
    action: Literal["approve", "correct", "override"]
    field: str | None = None
    rule_id: str | None = None
    value: Annotated[str, Field(max_length=500)] | None = None
    reason: Reason | None = None


class ReviewIn(BaseModel):
    form_version: int
    decisions: Annotated[list[DecisionIn], Field(max_length=50)] = []
    approve_form: bool = False
    reject_case: bool = False
    reject_reason: Reason | None = None
    action_id: ActionId


class SubmitIn(BaseModel):
    action_id: ActionId
    form_version: int


class SubmitOut(BaseModel):
    submission_id: str
    verified: bool


class ReopenIn(BaseModel):
    action_id: ActionId
    reason: Reason


class RetryIn(BaseModel):
    action_id: ActionId


class ActionErrorOut(BaseModel):
    """409: the action is not possible now. ``code`` names the reason (contracts/http-api.md)."""

    code: ActionErrorCode
    field: str | None = None
    rule_id: str | None = None


# ------------------------------------------------------------------ trace and summary (US5)
class SpanView(BaseModel):
    """One step, model call or tool call. Only non-personal columns: no document text."""

    span_id: str
    parent_id: str | None
    kind: Literal["step", "model_call", "tool_call"]
    name: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    model: str | None
    """The model that served the call."""
    summary: str
    """``ok``, or the error code (for example ``refusal`` or ``registry_unavailable``)."""


class TraceOut(BaseModel):
    spans: list[SpanView]


class SummaryOut(BaseModel):
    """Today's rates, over runs that finished processing (contracts/http-api.md)."""

    runs: int
    refusal_rate: float
    fallback_rate: float
    review_rate: float
    cost_usd: float
    budget_tokens_remaining: int
