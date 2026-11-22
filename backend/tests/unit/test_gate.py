"""The gate picks one route per run (US3): the "Confidence and routing" table in
specs/001-licence-to-kyb/test-cases.md, then its Hypothesis properties."""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from licence_kyb.nodes.gate import decide_route

from licence_kyb.rules.base import failed, not_applicable, passed
from licence_kyb.schemas.results import FILE_REASONS, RuleResult, reason_entry

AGREE = {"expiry_date": True, "licence_number": True}


def clean_rules() -> list[RuleResult]:
    return [
        passed("expiry", "expiry_date"),
        passed("evidence", "expiry_date", severity="warn"),
        passed("number_format", "licence_number"),
        passed("registry", "licence_number", "expiry_date"),
    ]


def replace(rules: list[RuleResult], *new: RuleResult) -> list[RuleResult]:
    """The rules with each rule in ``new`` replacing the one with the same ID."""
    ids = {r.rule_id for r in new}
    return [r for r in rules if r.rule_id not in ids] + list(new)


EXPIRED = failed("expiry", "expiry_date", severity="block", reason="expired")
EVIDENCE_FAILS = failed("evidence", "expiry_date", severity="warn", reason="evidence_mismatch")
NO_REGISTRY = not_applicable("registry", "licence_number", "expiry_date")

ROWS: list[tuple[str, dict[str, Any], str, set[str]]] = [
    ("every rule passes", {}, "ready", set()),
    (
        "expired; both readings agree; the evidence check passes",
        {"rules": replace(clean_rules(), EXPIRED, NO_REGISTRY)},
        "reject",
        {"expired"},
    ),
    (
        "expired in the primary reading only",
        {
            "rules": replace(clean_rules(), EXPIRED, NO_REGISTRY),
            "agreement": {"expiry_date": False},
        },
        "needs_review",
        {"expiry_uncertain"},
    ),
    (
        "expired in both readings; evidence fails; no QR or registry",
        {"rules": replace(clean_rules(), EXPIRED, EVIDENCE_FAILS, NO_REGISTRY)},
        "needs_review",
        {"expiry_uncertain"},
    ),
    (
        "expired; the registry confirms the same expiry",
        {
            "rules": replace(clean_rules(), EXPIRED, EVIDENCE_FAILS),
            "agreement": {"expiry_date": False},
        },
        "reject",
        {"expired"},
    ),
    (
        "expires in 10 days",
        {
            "rules": replace(
                clean_rules(),
                failed("expiry", "expiry_date", severity="warn", reason="near_expiry"),
            )
        },
        "needs_review",
        {"near_expiry"},
    ),
    (
        "a field below its confidence threshold",
        {
            "rules": [
                *clean_rules(),
                failed("confidence", "expiry_date", severity="warn", reason="low_confidence"),
            ]
        },
        "needs_review",
        {"low_confidence"},
    ),
    (
        "high-risk activity",
        {
            "rules": [
                *clean_rules(),
                failed("activity", "activities", severity="warn", reason="high_risk_activity"),
            ]
        },
        "needs_review",
        {"high_risk_activity"},
    ),
    (
        "not a licence (moa)",
        {"run_reasons": ["out_of_scope"], "rules": []},
        "reject",
        {"out_of_scope"},
    ),
    (
        "document unclear",
        {"run_reasons": ["unclear_document"], "rules": []},
        "needs_review",
        {"unclear_document"},
    ),
    (
        "authority unknown",
        {"run_reasons": ["unknown_authority"]},
        "needs_review",
        {"unknown_authority"},
    ),
    (
        "clean IFZA licence: no register to check",
        {"rules": replace(clean_rules(), NO_REGISTRY)},
        "ready",
        set(),
    ),
    (
        "no shares printed",
        {
            "rules": [
                *clean_rules(),
                failed("ubo", "people", severity="warn", reason="ubo_needs_examination"),
            ]
        },
        "needs_review",
        {"ubo_needs_examination"},
    ),
    (
        "a fallback model read the licence",
        {"run_reasons": ["fallback_model"]},
        "needs_review",
        {"fallback_model"},
    ),
]


def route_of(case: dict[str, Any]) -> tuple[str, set[str]]:
    decision = decide_route(
        run_reasons=[reason_entry(c) for c in case.get("run_reasons", [])],
        rule_results=case.get("rules", clean_rules()),
        agreement=case.get("agreement", AGREE),
    )
    return decision["route"], {r["code"] for r in decision["reasons"]}


@pytest.mark.parametrize(("name", "case", "route", "codes"), ROWS, ids=[r[0] for r in ROWS])
def test_the_gate_routes_each_row_of_the_table(
    name: str, case: dict[str, Any], route: str, codes: set[str]
) -> None:
    got_route, got_codes = route_of(case)

    assert got_route == route, name
    assert codes <= got_codes, name


# ------------------------------------------------------------------ properties
OUTCOMES = st.sampled_from(["passed", "failed", "could_not_run", "not_applicable"])
REASONS = st.sampled_from(
    [
        "expired",
        "near_expiry",
        "number_format",
        "qr_mismatch",
        "registry_not_found",
        "registry_unavailable",
        "evidence_mismatch",
        "low_confidence",
        "high_risk_activity",
    ]
)
FIELDS = st.sampled_from(["expiry_date", "licence_number", "trade_name_en", "people"])


@st.composite
def rule_results(draw: st.DrawFn) -> RuleResult:
    outcome = draw(OUTCOMES)
    rule_id = draw(st.sampled_from(["expiry", "evidence", "registry", "qr", "number_format"]))
    return RuleResult(
        rule_id=rule_id,
        fields=(draw(FIELDS),),
        severity=draw(st.sampled_from(["block", "warn"])),
        outcome=outcome,
        reason_code=draw(REASONS) if outcome in ("failed", "could_not_run") else None,
    )


RUN_REASONS = st.lists(
    st.sampled_from(
        [
            *sorted(FILE_REASONS),
            "out_of_scope",
            "unclear_document",
            "unknown_authority",
            "fallback_model",
            "processing_failed",
        ]
    ),
    max_size=2,
)
AGREEMENT = st.dictionaries(st.sampled_from(["expiry_date", "licence_number"]), st.booleans())


@given(st.lists(rule_results(), max_size=8), RUN_REASONS, AGREEMENT)
def test_a_failed_blocking_check_never_routes_ready(
    rules: list[RuleResult], run_reasons: list[str], agreement: dict[str, bool]
) -> None:
    decision = decide_route(
        run_reasons=[reason_entry(c) for c in run_reasons],
        rule_results=rules,
        agreement=agreement,
    )

    if any(r.severity == "block" and r.counts_as_failed for r in rules):
        assert decision["route"] != "ready"


@given(st.lists(rule_results(), max_size=8), RUN_REASONS, AGREEMENT)
def test_reject_needs_a_file_reason_out_of_scope_or_a_corroborated_expiry(
    rules: list[RuleResult], run_reasons: list[str], agreement: dict[str, bool]
) -> None:
    decision = decide_route(
        run_reasons=[reason_entry(c) for c in run_reasons],
        rule_results=rules,
        agreement=agreement,
    )

    if decision["route"] == "reject":
        codes = {r["code"] for r in decision["reasons"]}
        assert codes & (FILE_REASONS | {"out_of_scope", "expired"})


@given(st.lists(rule_results(), max_size=8), RUN_REASONS, AGREEMENT)
def test_one_route_and_reasons_unless_ready(
    rules: list[RuleResult], run_reasons: list[str], agreement: dict[str, bool]
) -> None:
    decision = decide_route(
        run_reasons=[reason_entry(c) for c in run_reasons],
        rule_results=rules,
        agreement=agreement,
    )

    assert decision["route"] in ("ready", "needs_review", "reject")
    assert (decision["route"] == "ready") == (decision["reasons"] == [])
