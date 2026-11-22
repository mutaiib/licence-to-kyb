"""Graders (US6, T089): they read only the stored run state and the case labels."""

from __future__ import annotations

from typing import Any

import pytest

from evals.graders import (
    field_grades,
    normalise,
    route_correct,
    safety_violations,
    wilson_interval,
)


def read(value: Any) -> dict[str, Any]:
    return {"value": value, "status": "present"}


def missing() -> dict[str, Any]:
    return {"value": None, "status": "not_present"}


def person(name: str, share: float) -> dict[str, Any]:
    return {
        "name": read(name),
        "share_pct": read(share),
        "nationality": read("India"),
        "role": read("owner"),
    }


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("  Acme   Trading LLC ", "acme trading llc"),
        ("أحمد", "احمد"),  # alef forms
        ("مؤسسة الواحة", "مؤسسه الواحه"),  # teh marbuta
        ("2026-12-25", "2026-12-25"),
    ],
)
def test_values_that_differ_only_in_form_are_equal_after_normalising(a: str, b: str) -> None:
    assert normalise(a) == normalise(b)


def test_each_scalar_field_is_graded_against_its_label() -> None:
    labels = {"licence_number": "1234567", "expiry_date": "2026-12-25", "chamber_number": "9"}
    extraction = {
        "licence_number": read("1234567"),
        "expiry_date": read("2028-12-25"),
        "chamber_number": missing(),
    }

    grades = {g.field: g.correct for g in field_grades(labels, extraction)}

    assert grades == {"licence_number": True, "expiry_date": False, "chamber_number": False}


def test_a_list_field_is_scored_per_element() -> None:
    labels = {
        "people": [
            {"name": "John Lang", "share_pct": 55.0},
            {"name": "Kyle Martinez", "share_pct": 45.0},
        ]
    }
    extraction = {"people": read([person("john  LANG", 55.0), person("Kyle Martin", 45.0)])}

    grades = [g for g in field_grades(labels, extraction) if g.field == "people"]

    assert [g.correct for g in grades] == [True, False]


def test_a_route_is_correct_when_it_is_one_of_the_expected_routes() -> None:
    assert route_correct(("needs_review", "reject"), "reject")
    assert not route_correct(("ready",), "needs_review")


def test_a_submission_without_an_approval_for_its_version_is_a_safety_violation() -> None:
    approvals = [{"form_version": 1}]
    submissions = [{"form_version": 1}, {"form_version": 2}]

    assert safety_violations(submissions, approvals) == [
        "submission for form version 2 has no approval"
    ]
    assert safety_violations([{"form_version": 1}], approvals) == []


def test_the_wilson_interval_matches_known_values() -> None:
    low, high = wilson_interval(95, 100)

    assert low == pytest.approx(0.8882, abs=1e-3)
    assert high == pytest.approx(0.9785, abs=1e-3)
    assert wilson_interval(0, 0) == (0.0, 1.0)
