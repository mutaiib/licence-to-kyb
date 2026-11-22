"""Rule properties over generated inputs (test-cases.md, "Properties"; S4 AC2: >= 500 each)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from licence_kyb.rules import RegistryResult, RuleContext, run_rules
from tests.builders import extraction, field, person

TODAY = date(2026, 6, 1)
PROFILE = settings(max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def lookup(number: str, authority: str) -> RegistryResult:
    return RegistryResult(found=True, status="active")


def ctx(ex: Any, authority: str = "DET") -> RuleContext:
    return RuleContext(
        extraction=ex,
        authority=authority,
        today=TODAY,
        ocr_text="",
        qr_payload=None,
        registry=lookup,
        applicant_name="Acme General Trading LLC",
    )


@PROFILE
@given(days_before=st.integers(min_value=0, max_value=5000))
def test_any_expiry_on_or_before_today_is_blocked(days_before: int) -> None:
    expiry = TODAY - timedelta(days=days_before)
    ex = extraction(
        expiry_date=field(expiry.isoformat()),
        issue_date=field((expiry - timedelta(days=365)).isoformat()),
        establishment_date=field((expiry - timedelta(days=400)).isoformat()),
    )
    (result,) = [r for r in run_rules(ctx(ex)) if r.rule_id == "expiry"]
    assert (result.outcome, result.severity, result.reason_code) == ("failed", "block", "expired")


@PROFILE
@given(
    shares=st.lists(st.floats(min_value=0, max_value=100, allow_nan=False), min_size=1, max_size=5)
)
def test_shares_outside_the_tolerance_always_fail_and_inside_always_pass(
    shares: list[float],
) -> None:
    people = [person(f"P{i}", share=round(s, 2)) for i, s in enumerate(shares)]
    ex = extraction(people=field(people))
    total = sum(round(s, 2) for s in shares)
    (result,) = [r for r in run_rules(ctx(ex)) if r.rule_id == "shares_total"]
    if abs(total - 100) > 0.5:
        assert result.outcome == "failed"
    else:
        assert result.outcome == "passed"


names = st.text(alphabet=st.characters(categories=["L", "N", "Zs", "P"]), min_size=1, max_size=40)
maybe = st.one_of(st.none(), names)


@PROFILE
@given(
    number=maybe,
    trade=maybe,
    arabic=maybe,
    authority=st.sampled_from(["DET", "ADDED", "DMCC", "IFZA", "RAKEZ"]),
    form=st.sampled_from(["llc", "sole_establishment", "fze", "other"]),
    people_status=st.sampled_from(["present", "not_present", "unclear"]),
    ocr=st.one_of(st.none(), names),
)
def test_rules_never_raise_and_every_failure_names_a_field_and_a_reason(
    *,
    number: str | None,
    trade: str | None,
    arabic: str | None,
    authority: str,
    form: str,
    people_status: str,
    ocr: str | None,
) -> None:
    people = (
        field([person("A", share=None)])
        if people_status == "present"
        else field(None, status=people_status)
    )
    ex = extraction(
        licence_number=field(number),
        trade_name_en=field(trade),
        trade_name_ar=field(arabic),
        legal_form=field(form),
        people=people,
    )
    context = RuleContext(
        extraction=ex,
        authority=authority,
        today=TODAY,
        ocr_text=ocr,
        qr_payload=number,
        registry=lookup,
        applicant_name=trade or "",
    )

    results = run_rules(context)

    assert results
    for r in results:
        assert r.outcome in {"passed", "failed", "could_not_run", "not_applicable"}
        if r.outcome in {"failed", "could_not_run"}:
            assert r.fields, r
            assert r.reason_code is not None, r
