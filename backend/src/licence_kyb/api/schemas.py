"""API bodies (contracts/http-api.md). The OpenAPI schema and the frontend types come from here."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from licence_kyb.schemas.results import ReasonCode

RunStatus = Literal[
    "received", "processing", "rejected", "awaiting_review", "awaiting_submit", "submitted", "done"
]
FieldViewState = Literal[
    "passed", "flagged", "approved", "corrected", "overridden", "needs_examination"
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


class StepView(BaseModel):
    name: str
    state: Literal["done", "running", "pending", "skipped"]
    duration_ms: int | None = None


class EvidenceBox(BaseModel):
    page: int
    x: float
    y: float
    w: float
    h: float


class RuleView(BaseModel):
    rule_id: str
    severity: Literal["block", "warn"]
    outcome: Literal["passed", "failed", "could_not_run", "not_applicable"]
    reason_code: ReasonCode | None
    overridable: bool
    detail: dict[str, str] = {}


class ConfidenceView(BaseModel):
    score: float
    threshold: float
    signals: dict[str, float]


class FormFieldView(BaseModel):
    value: Any
    state: FieldViewState
    origin: Literal["read", "entered_by_reviewer"] = "read"
    evidence_quote: str | None = None
    evidence_box: EvidenceBox | None = None
    confidence: ConfidenceView | None = None
    rule_results: list[RuleView] = []
    model_rationale: str | None = None


class FormView(BaseModel):
    version: int
    fields: dict[str, FormFieldView]


class RunView(BaseModel):
    run_id: str
    status: RunStatus
    steps: list[StepView]
    route: Literal["ready", "needs_review", "reject"] | None
    reasons: list[ReasonView]
    form: FormView | None
    required_documents: list[str]
    pages: int


class RunSummary(BaseModel):
    run_id: str
    created_at: str
    applicant_name: str
    route: str | None
    status: RunStatus
    cost_usd: float
    duration_ms: int


class RunList(BaseModel):
    runs: list[RunSummary]
