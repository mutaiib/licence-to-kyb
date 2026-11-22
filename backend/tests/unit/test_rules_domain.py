"""Domain checks found by a review of the rules against UAE licences (review round 3).

Each row is one input and the outcome a reviewer expects. Today is 2026-06-01."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from typing import Any

import pytest

from licence_kyb.clock import FixedClock
from licence_kyb.nodes import review
from licence_kyb.nodes.map_form import build_form
from licence_kyb.rules import run_rules
from licence_kyb.schemas.licence import TradeLicenceExtraction
from tests.builders import extraction, field, person
from tests.unit.test_rules import context, outcome, registry, result


# ---------------------------------------------------------------- high-risk activities
def with_activity(en: str, ar: str | None = None, code: str = "0000.00") -> Any:
    act = {"code": field(code), "description_en": field(en), "description_ar": field(ar)}
    data = extraction().model_dump(mode="json")
    return TradeLicenceExtraction.model_validate({**data, "activities": field([act])})


@pytest.mark.parametrize(
    ("en", "ar", "high_risk"),
    [
        ("Precious Metal Trading", None, True),
        ("Diamonds Trading", None, True),
        ("Bullion Trading", None, True),
        ("Gold Jewellery Trading", None, True),
        ("Money Changer", None, True),
        ("Exchange House", None, True),
        ("Hawala Services", None, True),
        ("Gen. Trading", None, True),
        ("Office Services", "التجارة العامة", True),
        ("Office Services", "تجارة عامة", True),
        ("Golden Sands Restaurant", None, False),
        ("Marigold Florist", None, False),
        ("Computer Programming", None, False),
    ],
)
def test_high_risk_activities_are_found_by_meaning_not_by_any_substring(
    en: str, ar: str | None, high_risk: bool
) -> None:
    got = outcome(run_rules(context(extraction=with_activity(en, ar))), "high_risk_activity")
    assert (got[0] == "failed") is high_risk


# ---------------------------------------------------------------- today in the UAE
def test_today_is_the_date_in_the_uae() -> None:
    """01:00 on 1 June in Dubai is still 31 May in UTC; the licence day is the UAE day."""
    assert FixedClock(datetime(2026, 5, 31, 21, 0, tzinfo=UTC)).today() == date(2026, 6, 1)


# ---------------------------------------------------------------- registry status
def test_a_licence_the_register_shows_as_cancelled_is_blocked() -> None:
    got = outcome(run_rules(context(registry=registry("cancelled"))), "registry")
    assert got == ("failed", "block", "registry_inactive")


# ---------------------------------------------------------------- QR code
@pytest.mark.parametrize(
    ("payload", "agrees"),
    [
        ("1234567", True),
        ("https://verify.example/licence?no=1234567&x=1", True),
        ("81234567", False),
        ("id=9912345670", False),
    ],
)
def test_the_qr_number_must_be_the_whole_licence_number(payload: str, agrees: bool) -> None:
    got = outcome(run_rules(context(qr_payload=payload)), "qr")
    assert (got[0] == "passed") is agrees


# ---------------------------------------------------------------- exact evidence
def evidence_of(results: Any, name: str) -> str:
    return str(next(r.outcome for r in results if r.rule_id == "evidence" and name in r.fields))


def test_a_truncated_identifier_is_not_found_inside_a_longer_one() -> None:
    ex = extraction(chamber_number=field("39353", quote="Chamber No 393530"))
    ctx = context(extraction=ex, ocr_text="Chamber No 393530\nExpiry Date 01/03/2027")

    assert evidence_of(run_rules(ctx), "chamber_number") == "failed"


@pytest.mark.parametrize(
    "printed",
    ["Expiry Date ٠١/٠٣/٢٠٢٧", "Expiry Date 1/3/2027", "Expiry Date 01.03.2027"],  # noqa: RUF001 - Arabic-Indic digits on purpose
)
def test_a_date_printed_another_way_is_still_found(printed: str) -> None:
    ex = extraction(expiry_date=field("2027-03-01", quote=printed))
    ctx = context(extraction=ex, ocr_text=f"{printed}\nLicence No 1234567")

    assert evidence_of(run_rules(ctx), "expiry_date") == "passed"


def test_arabic_marks_do_not_hide_an_arabic_name() -> None:
    printed = "شَرِكَةُ الأُفُــــقِ لِلتِّجَارَةِ"  # diacritics and a stretched letter
    ex = extraction(trade_name_ar=field("شركة الأفق للتجارة", quote=printed))
    ctx = context(extraction=ex, ocr_text=printed)

    assert evidence_of(run_rules(ctx), "trade_name_ar") == "passed"


# ---------------------------------------------------------------- licence number format
@pytest.mark.parametrize(
    ("authority", "number"),
    [
        ("ADDED", "CN–1002016"),  # noqa: RUF001 - an en dash on purpose
        ("ADDED", "cn-1002016"),
        ("DMCC", "DMCC 30894"),
        ("DET", "١٢٣٤٥٦٧"),
    ],
)
def test_a_number_written_with_other_dashes_case_spaces_or_digits_matches(
    authority: str, number: str
) -> None:
    ex = extraction(licence_number=field(number))
    ctx = context(extraction=ex, authority=authority, qr_payload=None)

    assert outcome(run_rules(ctx), "number_format")[0] == "passed"


def test_a_number_against_an_inferred_pattern_can_be_overridden_by_a_reviewer() -> None:
    """DET's pattern is inferred from samples: an older 6-digit number may be real."""
    ex = extraction(licence_number=field("123456"))
    rule = result(run_rules(context(extraction=ex, qr_payload=None)), "number_format")
    assert (rule.outcome, rule.overridable) == ("failed", True)

    state = {"rule_results": [rule.model_dump(mode="json")]}
    decision = {"action": "override", "rule_id": "number_format", "reason": "Older DET number"}
    review.check_review_target(state, decision)  # no refusal


def test_a_number_against_a_confirmed_pattern_cannot_be_overridden() -> None:
    ex = extraction(licence_number=field("CN-12"))
    ctx = context(extraction=ex, authority="ADDED", qr_payload=None)

    assert result(run_rules(ctx), "number_format").overridable is False


# ---------------------------------------------------------------- applicant name
@pytest.mark.parametrize(
    ("licence_en", "licence_ar", "applicant", "matches"),
    [
        ("Al Noor General Trading LLC", None, "AlNoor General Trading L.L.C", True),
        ("Zenith Trading LLC", None, "Zenith Foods Trading LLC", False),
        ("Al Noor Est", "مؤسسة النور", "مؤسسة النور", True),
    ],
)
def test_the_applicant_name_is_compared_by_its_distinctive_words(
    licence_en: str, licence_ar: str | None, applicant: str, matches: bool
) -> None:
    ex = extraction(trade_name_en=field(licence_en), trade_name_ar=field(licence_ar))
    got = outcome(run_rules(context(extraction=ex, applicant_name=applicant)), "applicant_name")
    assert (got[0] == "passed") is matches


# ---------------------------------------------------------------- an expiry in one reading
def test_an_expiry_read_as_past_only_by_the_second_reading_is_uncertain() -> None:
    ctx = context(secondary_expiry=date(2026, 5, 1))  # the first reading says 2027-03-01

    assert outcome(run_rules(ctx), "expiry") == ("failed", "block", "expiry_uncertain")


# ---------------------------------------------------------------- documents to request
def docs(form: Any) -> Counter[str]:
    return Counter(d.document for d in form.required_documents)


def test_every_owner_needs_an_identity_document_when_no_shares_are_printed() -> None:
    people = [person("A", share=None), person("B", share=None)]
    form = build_form(extraction(people=field(people)), [], authority="DET", version=1)

    assert docs(form)["identity_document"] == 2


def test_a_memorandum_is_requested_when_the_legal_form_is_unclear() -> None:
    ex = extraction(legal_form=field(None, status="unclear"))
    form = build_form(ex, [], authority="DET", version=1)

    assert docs(form)["memorandum_of_association"] == 1
