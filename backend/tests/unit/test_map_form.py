"""Draft KYB form mapping, from the "Form filling" table in test-cases.md (FR-031, S8)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from licence_kyb.nodes.map_form import build_form, read_values
from licence_kyb.schemas.results import RuleResult
from tests.builders import extraction, field, person


def docs(form: Any) -> Counter[str]:
    return Counter(d.document for d in form.required_documents)


def flagged(field_name: str, reason: str = "near_expiry") -> RuleResult:
    return RuleResult(
        rule_id="x", fields=(field_name,), severity="warn", outcome="failed", reason_code=reason
    )


def test_det_llc_with_two_owners_and_a_separate_manager() -> None:
    people = [
        person("A", share=60.0),
        person("B", share=40.0),
        person("M", role="manager", share=None),
    ]
    form = build_form(extraction(people=field(people)), [], authority="DET", version=1)

    assert len(form.beneficial_owners) == 2
    assert len(form.controllers) == 3
    assert docs(form) == Counter(
        {"memorandum_of_association": 1, "identity_document": 3, "tenancy_contract_ejari": 1}
    )


def test_added_llc_with_one_owner_who_is_also_the_manager() -> None:
    people = [person("A", share=100.0), person("A", role="manager", share=None)]
    form = build_form(
        extraction(people=field(people), licence_number=field("CN-1234567")),
        [],
        authority="ADDED",
        version=1,
    )

    assert len(form.beneficial_owners) == 1
    assert len(form.controllers) == 1
    assert docs(form) == Counter(
        {"memorandum_of_association": 1, "identity_document": 1, "tenancy_contract_tawtheeq": 1}
    )


def test_dmcc_fze_with_one_owner_who_is_also_the_manager() -> None:
    people = [person("A", share=100.0), person("A", role="manager", share=None)]
    ex = extraction(
        people=field(people), legal_form=field("fze"), licence_number=field("DMCC-30894")
    )
    form = build_form(ex, [], authority="DMCC", version=1)

    assert docs(form) == Counter({"identity_document": 1, "free_zone_lease": 1})


def test_only_owners_with_25_percent_or_more_are_beneficial_owners() -> None:
    people = [person("A", share=20.0), person("B", share=20.0), person("C", share=60.0)]
    form = build_form(extraction(people=field(people)), [], authority="DET", version=1)

    assert [p.name for p in form.beneficial_owners] == ["C"]


def test_no_printed_shares_leaves_owners_for_examination_and_requires_the_moa() -> None:
    people = [person("M1", role="manager", share=None), person("M2", role="manager", share=None)]
    ex = extraction(people=field(people), legal_form=field("sole_establishment"))
    form = build_form(ex, [], authority="DET", version=1)

    assert form.beneficial_owners == ()
    assert form.field_states["beneficial_owners"] == "needs_examination"
    assert len(form.controllers) == 2
    assert docs(form)["memorandum_of_association"] == 1


def test_people_with_the_same_name_but_different_nationality_are_not_merged() -> None:
    people = [
        person("Ali Hassan", nationality="United Arab Emirates", share=100.0),
        person("Ali Hassan", nationality="Egypt", role="manager", share=None),
    ]
    form = build_form(extraction(people=field(people)), [], authority="DET", version=1)

    assert len(form.controllers) == 2


def test_a_flagged_unapproved_value_is_left_empty_for_examination() -> None:
    form = build_form(extraction(), [flagged("expiry_date")], authority="DET", version=1)

    assert form.expiry_date is None
    assert form.field_states["expiry_date"] == "needs_examination"
    assert form.field_states["licence_number"] == "passed"


def test_a_check_that_could_not_run_also_leaves_its_fields_for_examination() -> None:
    could_not = RuleResult(
        rule_id="registry",
        fields=("licence_number",),
        severity="block",
        outcome="could_not_run",
        reason_code="registry_unavailable",
        overridable=True,
    )
    form = build_form(extraction(), [could_not], authority="DET", version=1)

    assert form.licence_number is None
    assert form.field_states["licence_number"] == "needs_examination"


@settings(max_examples=200, deadline=None)
@given(
    shares=st.lists(
        st.one_of(st.none(), st.floats(0, 100, allow_nan=False)), min_size=1, max_size=5
    )
)
def test_beneficial_owners_are_exactly_the_owners_with_25_percent_or_more(
    shares: list[float | None],
) -> None:
    people = [person(f"P{i}", share=s) for i, s in enumerate(shares)]
    form = build_form(extraction(people=field(people)), [], authority="DET", version=1)

    if all(s is None for s in shares):
        assert form.beneficial_owners == ()
    else:
        expected = {f"P{i}" for i, s in enumerate(shares) if s is not None and s >= 25}
        assert {p.name for p in form.beneficial_owners} == expected


def test_mapping_the_same_extraction_twice_gives_identical_forms() -> None:
    ex = extraction()
    assert build_form(ex, [], authority="DET", version=1) == build_form(
        ex, [], authority="DET", version=1
    )


def test_the_read_values_list_every_person_in_the_same_shape_as_the_form() -> None:
    people = [person("A", share=60.0), person("M", role="manager", share=None)]

    values = read_values(extraction(people=field(people)))

    owners = values["beneficial_owners"]
    assert isinstance(owners, tuple)
    assert [(p.name, p.roles, p.share_pct) for p in owners] == [
        ("A", ("owner",), 60.0),
        ("M", ("manager",), None),
    ]
    assert values["controllers"] == owners
