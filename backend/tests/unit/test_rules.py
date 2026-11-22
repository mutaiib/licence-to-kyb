"""Validation rules, row by row from the "Checks" table in test-cases.md.

Assertions use outcome, severity and reason code only. Today is 2026-06-01.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from licence_kyb.rules import RegistryResult, RuleContext, run_rules
from licence_kyb.schemas.results import RuleResult
from tests.builders import extraction, field, person

TODAY = date(2026, 6, 1)


def registry(status: str = "active", expiry: str = "2027-03-01") -> Any:
    def lookup(number: str, authority: str) -> RegistryResult:
        if status == "unavailable":
            raise TimeoutError("register did not answer")
        if status == "not_found":
            return RegistryResult(found=False)
        return RegistryResult(found=True, status=status, expiry_date=date.fromisoformat(expiry))

    return lookup


def ocr_of(ex: Any) -> str:
    """OCR text that contains every quote, so evidence checks pass unless a test says not."""
    quotes: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("evidence_quote"):
                quotes.append(node["evidence_quote"])
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(ex.model_dump(mode="json"))
    return "\n".join(quotes)


def context(**overrides: Any) -> RuleContext:
    ex = overrides.get("extraction", extraction())
    base: dict[str, Any] = {
        "extraction": ex,
        "authority": "DET",
        "today": TODAY,
        "ocr_text": ocr_of(ex),
        "qr_payload": "1234567",
        "registry": registry(),
        "applicant_name": "Acme General Trading LLC",
    }
    base.update(overrides)
    return RuleContext(**base)


def result(results: list[RuleResult], rule_id: str) -> RuleResult:
    matching = [r for r in results if r.rule_id == rule_id]
    assert len(matching) == 1, f"expected one {rule_id} result, got {matching}"
    return matching[0]


def outcome(results: list[RuleResult], rule_id: str) -> tuple[str, str | None, str | None]:
    r = result(results, rule_id)
    return (r.outcome, r.severity if r.outcome != "passed" else None, r.reason_code)


# ---------------------------------------------------------------- expiry
@pytest.mark.parametrize(
    ("expiry", "expected"),
    [
        ("2026-05-31", ("failed", "block", "expired")),
        ("2026-06-01", ("failed", "block", "expired")),
        ("2026-06-30", ("failed", "warn", "near_expiry")),
        ("2026-07-01", ("passed", None, None)),
    ],
)
def test_expiry(expiry: str, expected: tuple[str, str | None, str | None]) -> None:
    ctx = context(
        extraction=extraction(expiry_date=field(expiry), issue_date=field("2025-07-01")),
        registry=registry(expiry=expiry),
    )
    assert outcome(run_rules(ctx), "expiry") == expected


# ---------------------------------------------------------------- number format
@pytest.mark.parametrize(
    ("authority", "number", "expected"),
    [
        ("ADDED", "CN-1002016", ("passed", None, None)),
        ("ADDED", "CN-100201", ("failed", "block", "number_format")),
        ("DET", "1234567", ("passed", None, None)),
    ],
)
def test_number_format(authority: str, number: str, expected: tuple[str, ...]) -> None:
    ctx = context(
        authority=authority, extraction=extraction(licence_number=field(number)), qr_payload=None
    )
    assert outcome(run_rules(ctx), "number_format") == expected


# ---------------------------------------------------------------- ownership
@pytest.mark.parametrize(
    ("shares", "expected"),
    [
        ([50.0, 50.0], ("passed", None, None)),
        ([50.0, 40.0], ("failed", "block", "shares_total")),
        ([33.3, 33.3, 33.3], ("passed", None, None)),
        ([None, None], ("not_applicable", "block", None)),
    ],
)
def test_shares_total(shares: list[float | None], expected: tuple[str, ...]) -> None:
    people = [person(f"Owner {i}", share=s) for i, s in enumerate(shares)]
    ctx = context(extraction=extraction(people=field(people), legal_form=field("llc")))
    assert outcome(run_rules(ctx), "shares_total") == expected


def test_sole_establishment_with_two_owners_is_blocked() -> None:
    people = [person("A", share=50.0), person("B", share=50.0)]
    ctx = context(
        extraction=extraction(people=field(people), legal_form=field("sole_establishment"))
    )
    assert outcome(run_rules(ctx), "sole_owner_count") == ("failed", "block", "sole_owner_count")


def test_no_printed_shares_flags_beneficial_owners_for_examination() -> None:
    people = [person("A", share=None), person("B", role="manager", share=None)]
    ctx = context(extraction=extraction(people=field(people), legal_form=field("llc")))
    assert outcome(run_rules(ctx), "ubo") == ("failed", "warn", "ubo_needs_examination")


def test_unreadable_owners_table_is_flagged_not_treated_as_no_owners() -> None:
    ctx = context(extraction=extraction(people=field(None, status="unclear")))
    results = run_rules(ctx)
    assert outcome(results, "owners") == ("failed", "warn", "owners_unclear")


# ---------------------------------------------------------------- legal form, Arabic name
def test_free_zone_cannot_issue_a_mainland_llc() -> None:
    ctx = context(authority="DMCC", extraction=extraction(licence_number=field("DMCC-30894")))
    assert outcome(run_rules(ctx), "legal_form") == ("failed", "block", "legal_form_not_allowed")


def test_missing_arabic_name_is_flagged_where_the_authority_shows_one() -> None:
    ctx = context(extraction=extraction(trade_name_ar=field(None, status="not_present")))
    assert outcome(run_rules(ctx), "arabic_name") == ("failed", "warn", "arabic_name_missing")


# ---------------------------------------------------------------- activities
def test_general_trading_is_a_high_risk_activity() -> None:
    acts = [{"code": "4690.01", "en": "General Trading"}]
    ctx = context(extraction=extraction(activities=acts))
    assert outcome(run_rules(ctx), "high_risk_activity") == (
        "failed",
        "warn",
        "high_risk_activity",
    )


# ---------------------------------------------------------------- evidence
def test_value_not_in_its_own_quote_fails_the_evidence_check() -> None:
    ex = extraction(expiry_date=field("2028-12-25", quote="Expiry Date 25/12/2026"))
    ctx = context(
        extraction=ex, ocr_text="Expiry Date 25/12/2026", registry=registry(expiry="2028-12-25")
    )
    evidence = [r for r in run_rules(ctx) if r.rule_id == "evidence" and "expiry_date" in r.fields]
    assert [(r.outcome, r.reason_code) for r in evidence] == [("failed", "evidence_mismatch")]


def test_value_entered_by_a_reviewer_skips_the_evidence_check() -> None:
    ex = extraction(licence_number=field("1234567", origin="entered_by_reviewer"))
    ctx = context(extraction=ex, ocr_text="nothing relevant here")
    evidence = [
        r for r in run_rules(ctx) if r.rule_id == "evidence" and "licence_number" in r.fields
    ]
    assert [r.outcome for r in evidence] == ["not_applicable"]


# ---------------------------------------------------------------- QR and registry
def test_qr_number_that_differs_from_the_printed_one_is_blocked() -> None:
    ctx = context(qr_payload="1234561")
    assert outcome(run_rules(ctx), "qr") == ("failed", "block", "qr_mismatch")


@pytest.mark.parametrize(
    ("status", "authority", "expected", "overridable"),
    [
        ("not_found", "DET", ("failed", "block", "registry_not_found"), False),
        ("unavailable", "DET", ("could_not_run", "block", "registry_unavailable"), True),
        ("active", "IFZA", ("not_applicable", "block", None), False),
    ],
)
def test_registry(
    status: str, authority: str, expected: tuple[str, ...], overridable: bool
) -> None:
    number = "12345" if authority == "IFZA" else "1234567"
    ctx = context(
        authority=authority,
        registry=registry(status),
        qr_payload=None,
        extraction=extraction(
            licence_number=field(number), legal_form=field("fze" if authority == "IFZA" else "llc")
        ),
    )
    results = run_rules(ctx)
    assert outcome(results, "registry") == expected
    assert result(results, "registry").overridable is overridable


def test_registry_expiry_that_differs_from_the_licence_is_blocked() -> None:
    ctx = context(registry=registry(expiry="2026-09-01"))
    assert outcome(run_rules(ctx), "registry") == ("failed", "block", "registry_expiry_mismatch")


# ---------------------------------------------------------------- applicant name
@pytest.mark.parametrize(
    ("applicant", "licence", "passed"),
    [
        ("Acme Trading", "Zenith Foods LLC", False),
        ("ACME GENERAL TRADING L.L.C", "Acme General Trading LLC", True),
    ],
)
def test_applicant_name(applicant: str, licence: str, passed: bool) -> None:
    ctx = context(applicant_name=applicant, extraction=extraction(trade_name_en=field(licence)))
    got = outcome(run_rules(ctx), "applicant_name")
    assert got == (
        ("passed", None, None) if passed else ("failed", "warn", "applicant_name_mismatch")
    )


# ---------------------------------------------------------------- the whole set
def test_a_clean_licence_passes_every_applicable_rule() -> None:
    results = run_rules(context())
    failing = [r for r in results if r.counts_as_failed]
    assert failing == []


def test_a_rule_that_raises_becomes_could_not_run_and_the_others_still_run() -> None:
    ctx = replace(context(), registry=registry("unavailable"))
    results = run_rules(ctx)
    assert result(results, "registry").outcome == "could_not_run"
    assert result(results, "expiry").outcome == "passed"


def test_a_missing_critical_field_is_flagged_for_examination() -> None:
    ctx = context(extraction=extraction(licence_number=field(None, status="unclear")))
    required = [
        r for r in run_rules(ctx) if r.rule_id == "required" and "licence_number" in r.fields
    ]
    assert [(r.outcome, r.reason_code) for r in required] == [("failed", "low_confidence")]
