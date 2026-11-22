"""Comparing two reports (US6, T090): exactly the cases that changed are listed."""

from __future__ import annotations

from evals.compare import changed_cases


def case(route: str, codes: list[str], values: dict[str, bool]) -> dict[str, object]:
    return {"route": route, "reason_codes": codes, "fields": values}


def test_only_cases_whose_route_reasons_or_values_changed_are_listed() -> None:
    before = {
        "cases": {
            "a": case("ready", [], {"licence_number": True}),
            "b": case("needs_review", ["near_expiry"], {"expiry_date": True}),
            "c": case("needs_review", ["evidence_mismatch"], {"expiry_date": False}),
            "d": case("reject", ["expired"], {}),
        }
    }
    after = {
        "cases": {
            "a": case("ready", [], {"licence_number": True}),  # same
            "b": case("ready", [], {"expiry_date": True}),  # route and reasons changed
            "c": case("needs_review", ["evidence_mismatch"], {"expiry_date": True}),  # value fixed
            "d": case("reject", ["expired"], {}),  # same
        }
    }

    changes = changed_cases(before, after)

    assert sorted(changes) == ["b", "c"]
    assert changes["b"]["route"] == ("needs_review", "ready")
    assert changes["c"]["fields"] == {"expiry_date": (False, True)}


def test_a_case_in_only_one_report_is_listed() -> None:
    before = {"cases": {"a": case("ready", [], {})}}
    after = {"cases": {"a": case("ready", [], {}), "new": case("ready", [], {})}}

    assert list(changed_cases(before, after)) == ["new"]
