"""Schema behaviour, from the "Schemas and authority profiles" table in test-cases.md.

Tests assert outcomes: accepted or rejected, and which fields an error names.
They never assert message wording.
"""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from licence_kyb.schemas.licence import Field, Person, TradeLicenceExtraction


def present(value: Any, quote: str | None = None) -> dict[str, Any]:
    return {
        "value": value,
        "status": "present",
        "origin": "read",
        "evidence_quote": quote if quote is not None else str(value),
        "page": 1,
        "self_confidence": "high",
    }


def absent(status: str = "not_present") -> dict[str, Any]:
    return {
        "value": None,
        "status": status,
        "origin": "read",
        "evidence_quote": None,
        "page": None,
        "self_confidence": "unknown",
    }


def added_licence() -> dict[str, Any]:
    """Hand-labelled synthetic ADDED licence, shaped like the public example."""
    return {
        "licence_number": present("CN-1002016"),
        "unified_licence_number": present("501-1988-100005279"),
        "register_number": absent(),
        "chamber_number": present("3448"),
        "trade_name_en": present("Abu Dhabi Commercial Bank"),
        "trade_name_ar": present("بنك أبوظبي التجاري"),
        "legal_form": present("public_joint_stock", "Public Joint-Stock"),
        "licence_category": present("commercial", "Business"),
        "licence_type": present("Normal"),
        "issuing_authority": present("ADDED", "Abu Dhabi Economic Licence"),
        "establishment_date": present("02/07/1988"),
        "issue_date": present("19/11/2025"),
        "expiry_date": present("25/12/2026"),
        "activities": present(
            [
                {
                    "code": present("6419001.1"),
                    "description_en": present("Commercial Bank - Local"),
                    "description_ar": absent(),
                }
            ],
            "6419001.1 Commercial Bank - Local",
        ),
        "people": present(
            [
                {
                    "name": present("Example Holder"),
                    "nationality": present("United Arab Emirates"),
                    "role": present("owner", "Owner"),
                    "share_pct": absent(),
                }
            ],
            "Example Holder United Arab Emirates Owner",
        ),
        "address": present("Abu Dhabi, Al Khalidiya"),
    }


def error_fields(exc: ValidationError) -> set[str]:
    """Fields an error names: its location plus any structured ``fields`` it lists."""
    names: set[str] = set()
    for err in exc.errors():
        names.update(str(part) for part in err["loc"])
        names.update(err.get("ctx", {}).get("fields", []))
    return names


def test_valid_licence_record_is_accepted() -> None:
    record = TradeLicenceExtraction.model_validate(added_licence())

    assert record.licence_number.value == "CN-1002016"
    assert record.legal_form.value == "public_joint_stock"
    assert record.expiry_date.value == date(2026, 12, 25)


def test_dates_in_the_wrong_order_are_a_valid_record_for_the_rules_to_flag() -> None:
    data = added_licence()
    data["issue_date"] = present("25/12/2026")

    record = TradeLicenceExtraction.model_validate(data)

    assert record.issue_date.value == record.expiry_date.value


@pytest.mark.parametrize("share", [120.0, -1.0])
def test_share_outside_0_to_100_is_rejected_naming_share(share: float) -> None:
    person = added_licence()["people"]["value"][0]
    person["share_pct"] = present(share)

    with pytest.raises(ValidationError) as exc:
        Person.model_validate(person)

    assert "share_pct" in error_fields(exc.value)


@pytest.mark.parametrize("field_name", ["expiry_date", "people", "activities", "trade_name_ar"])
@pytest.mark.parametrize("status", ["not_present", "unclear"])
def test_any_field_can_be_absent_without_an_invented_value(field_name: str, status: str) -> None:
    data = added_licence()
    data[field_name] = absent(status)

    record = TradeLicenceExtraction.model_validate(data)

    field = getattr(record, field_name)
    assert field.status == status
    assert field.value is None


def test_unknown_legal_form_is_only_valid_as_other_with_original_text_kept() -> None:
    data = added_licence()
    data["legal_form"] = present("other", "Limited Partnership")
    record = TradeLicenceExtraction.model_validate(data)
    assert record.legal_form.value == "other"
    assert record.legal_form.evidence_quote == "Limited Partnership"

    data["legal_form"] = present("limited_partnership")
    with pytest.raises(ValidationError) as exc:
        TradeLicenceExtraction.model_validate(data)
    assert "legal_form" in error_fields(exc.value)


def test_impossible_calendar_date_is_rejected_naming_the_field() -> None:
    data = added_licence()
    data["expiry_date"] = present("31/02/2026")

    with pytest.raises(ValidationError) as exc:
        TradeLicenceExtraction.model_validate(data)

    assert "expiry_date" in error_fields(exc.value)


def test_value_entered_by_reviewer_needs_no_evidence_quote() -> None:
    field = Field[str].model_validate(
        {
            "value": "CN-1234567",
            "status": "present",
            "origin": "entered_by_reviewer",
            "evidence_quote": None,
            "page": None,
            "self_confidence": "unknown",
        }
    )

    assert field.value == "CN-1234567"


def test_read_value_without_evidence_quote_is_rejected() -> None:
    raw = present("CN-1234567")
    raw["evidence_quote"] = None

    with pytest.raises(ValidationError):
        Field[str].model_validate(raw)


def test_absent_field_with_a_value_is_rejected() -> None:
    raw = absent()
    raw["value"] = "something"

    with pytest.raises(ValidationError):
        Field[str].model_validate(raw)


def test_every_closed_list_in_the_schema_has_an_escape_value() -> None:
    escapes = {"other", "unclear", "unknown", "not_present"}
    schema = TradeLicenceExtraction.model_json_schema()

    enums: list[list[str]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "enum" in node:
                enums.append(node["enum"])
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(copy.deepcopy(schema))

    assert enums, "the schema has closed lists"
    for values in enums:
        if set(values) <= {"read", "entered_by_reviewer"}:
            continue  # origin is set by code, never by the model
        assert escapes & set(values), values
