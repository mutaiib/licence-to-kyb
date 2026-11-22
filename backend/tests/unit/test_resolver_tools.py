"""Resolver tools and their error results (US4): the "Tool error responses" table in
specs/001-licence-to-kyb/test-cases.md and its properties. Structure only, never wording."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

from licence_kyb.config import ResolverBudget
from licence_kyb.nodes.preprocess import Word
from licence_kyb.registry import RegistryUnavailableError
from licence_kyb.rules.base import RegistryResult, failed, passed
from licence_kyb.tools import ToolContext
from licence_kyb.tools.errors import ERROR_CODES, MAX_RESULT_CHARS, ToolResult
from licence_kyb.tools.runner import Budget, ToolRunner
from tests.builders import extraction, field

LIMITS = ResolverBudget(
    soft_turns=5,
    hard_turns=6,
    hard_rounds=2,
    soft_tokens=32_000,
    hard_tokens=40_000,
    soft_seconds=35,
    hard_seconds=45,
    hard_tool_calls=12,
)
VALUE_ERRORS = {
    "invalid_arguments",
    "field_out_of_scope",
    "page_not_found",
    "region_unreadable",
    "proposal_refused",
}
REQUIRED_KEYS = {
    "error_code",
    "what_failed",
    "why",
    "state",
    "retryable",
    "next_action",
    "allowed",
    "message",
}


def context(**overrides: Any) -> ToolContext:
    words = [
        Word(1, "Expiry", (0.55, 0.1, 0.62, 0.12), 0.96),
        Word(1, "Date", (0.63, 0.1, 0.68, 0.12), 0.95),
        Word(1, "25/12/2026", (0.7, 0.1, 0.8, 0.12), 0.71),
    ]
    base: dict[str, Any] = {
        "page_count": 1,
        "words": words,
        "extraction": extraction(expiry_date=field("2028-12-25", quote="Expiry Date 25/12/2028")),
        "rule_results": [
            failed("evidence", "expiry_date", severity="warn", reason="evidence_mismatch"),
            passed("number_format", "licence_number"),
        ],
        "failed_fields": ("expiry_date",),
        "authority": "DET",
        "registry": lambda number, authority: RegistryResult(
            found=True, status="active", expiry_date=date(2026, 12, 25)
        ),
        "reread": lambda page, region: "Expiry Date 25/12/2026",
    }
    return ToolContext(**{**base, **overrides})


def runner(ctx: ToolContext | None = None, budget: Budget | None = None) -> ToolRunner:
    return ToolRunner(ctx or context(), budget or Budget(LIMITS))


def error(result: ToolResult) -> dict[str, Any]:
    assert result.is_error
    body: dict[str, Any] = json.loads(result.content)
    assert set(body) >= REQUIRED_KEYS
    assert body["error_code"] in ERROR_CODES
    assert body["next_action"]
    if body["error_code"] in VALUE_ERRORS:
        assert body["allowed"]
    assert "Traceback" not in result.content
    assert len(result.content) <= MAX_RESULT_CHARS
    return body


# ------------------------------------------------------------------ the table
def test_a_page_outside_the_document_lists_the_pages_that_exist() -> None:
    body = error(
        runner().call(
            "licence_reread_region", {"page": 3, "field": "expiry_date", "region": "top_right"}
        )
    )

    assert body["error_code"] == "page_not_found"
    assert body["allowed"] == [1]


def test_a_field_that_passed_is_out_of_scope_and_the_failed_fields_are_listed() -> None:
    body = error(
        runner().call(
            "licence_reread_region", {"page": 1, "field": "trade_name_en", "region": "top_left"}
        )
    )

    assert body["error_code"] == "field_out_of_scope"
    assert body["allowed"] == ["expiry_date"]


def test_wrong_argument_types_name_the_argument_and_its_range() -> None:
    body = error(runner().call("licence_ocr_region", {"page": "one", "region": "top_right"}))

    assert body["error_code"] == "invalid_arguments"
    assert "page" in json.dumps(body["allowed"])


def test_an_unknown_tool_lists_the_tools_that_exist_and_runs_nothing() -> None:
    body = error(runner().call("submit_form", {}))

    assert body["error_code"] == "invalid_arguments"
    assert "licence_ocr_region" in body["allowed"]


def test_a_register_that_never_answers_is_unavailable_and_not_retryable() -> None:
    def down(number: str, authority: str) -> RegistryResult:
        raise RegistryUnavailableError(authority)

    body = error(
        runner(context(registry=down)).call(
            "licence_lookup_registry", {"licence_number": "1234567", "authority": "DET"}
        )
    )

    assert body["error_code"] == "registry_unavailable"
    assert body["retryable"] is False


def test_an_authority_with_no_register_is_an_answer_not_a_failure() -> None:
    result = runner().call(
        "licence_lookup_registry", {"licence_number": "12345", "authority": "IFZA"}
    )

    assert result.is_error is False
    assert result.error_code == "registry_not_applicable"


def test_a_failed_vision_re_read_points_to_the_ocr_tool() -> None:
    def refuses(page: int, region: str) -> str:
        raise RuntimeError("vision call failed")

    body = error(
        runner(context(reread=refuses)).call(
            "licence_reread_region", {"page": 1, "field": "expiry_date", "region": "top_right"}
        )
    )

    assert body["error_code"] == "vision_call_failed"
    assert "licence_ocr_region" in body["next_action"]


def test_the_same_call_twice_runs_once_and_says_so() -> None:
    calls: list[str] = []

    def counting(number: str, authority: str) -> RegistryResult:
        calls.append(number)
        return RegistryResult(found=False)

    r = runner(context(registry=counting))
    args = {"licence_number": "1234567", "authority": "DET"}
    first = r.call("licence_lookup_registry", args)
    second = r.call("licence_lookup_registry", args)

    assert calls == ["1234567"]
    assert second.notice_code == "duplicate_call"
    assert first.content in second.content


def test_a_proposal_for_a_field_that_passed_is_refused_and_not_recorded() -> None:
    r = runner()

    body = error(
        r.call(
            "propose_fix",
            {
                "field": "trade_name_en",
                "new_value": "X",
                "evidence_quote": "X",
                "self_confidence": "high",
                "rationale": "r",
            },
        )
    )

    assert body["error_code"] == "proposal_refused"
    assert body["allowed"] == ["expiry_date"]
    assert r.proposals == []


def test_an_unexpected_tool_failure_shows_no_internals() -> None:
    def broken(page: int, region: str) -> str:
        raise KeyError("/srv/app/secret_path.py")

    r = runner(context(reread=broken, words=None))  # type: ignore[arg-type]
    body = error(r.call("licence_ocr_region", {"page": 1, "region": "top_right"}))

    assert body["error_code"] == "tool_internal_error"
    assert "KeyError" not in json.dumps(body)
    assert ".py" not in json.dumps(body)


def test_at_a_soft_limit_the_result_tells_the_model_to_finish() -> None:
    budget = Budget(LIMITS)
    budget.charge_tokens(LIMITS.soft_tokens)

    result = runner(budget=budget).call("licence_get_validation_report", {})

    assert result.is_error is False
    assert result.notice_code == "budget_soft_limit"


def test_at_a_hard_limit_no_tool_runs() -> None:
    calls: list[str] = []

    def counting(number: str, authority: str) -> RegistryResult:
        calls.append(number)
        return RegistryResult(found=False)

    budget = Budget(LIMITS)
    budget.charge_tokens(LIMITS.hard_tokens)
    body = error(
        runner(context(registry=counting), budget).call(
            "licence_lookup_registry", {"licence_number": "1", "authority": "DET"}
        )
    )

    assert body["error_code"] == "budget_hard_limit"
    assert calls == []


# ------------------------------------------------------------------ answers
def test_the_ocr_tool_reports_each_word_with_its_confidence() -> None:
    result = runner().call("licence_ocr_region", {"page": 1, "region": "top_right"})

    assert not result.is_error
    assert "25/12/2026" in result.content
    assert "0.71" in result.content


def test_an_empty_region_is_unreadable_and_names_other_regions() -> None:
    body = error(runner().call("licence_ocr_region", {"page": 1, "region": "bottom_left"}))

    assert body["error_code"] == "region_unreadable"
    assert "bottom_left" not in body["allowed"]


def test_a_valid_proposal_is_recorded_for_later_checks() -> None:
    r = runner()

    result = r.call(
        "propose_fix",
        {
            "field": "expiry_date",
            "new_value": "25/12/2026",
            "evidence_quote": "Expiry Date 25/12/2026",
            "self_confidence": "high",
            "rationale": "re-read",
        },
    )

    assert not result.is_error
    assert [(p.field, p.new_value) for p in r.proposals] == [("expiry_date", "2026-12-25")]


@pytest.mark.parametrize("value", ["31/02/2026", "soon"])
def test_a_proposal_that_cannot_be_a_date_is_refused(value: str) -> None:
    r = runner()

    body = error(
        r.call(
            "propose_fix",
            {
                "field": "expiry_date",
                "new_value": value,
                "evidence_quote": "q",
                "self_confidence": "low",
                "rationale": "r",
            },
        )
    )

    assert body["error_code"] == "proposal_refused"
    assert r.proposals == []


def test_finish_ends_the_investigation() -> None:
    r = runner()

    r.call("finish", {"summary": "done"})

    assert r.finished


def test_every_result_stays_within_the_size_limit() -> None:
    long_words = [
        Word(1, "W" * 40, (0.6, 0.1 + i * 0.001, 0.7, 0.11 + i * 0.001), 0.9) for i in range(300)
    ]

    result = runner(context(words=long_words)).call(
        "licence_ocr_region", {"page": 1, "region": "top_right"}
    )

    assert len(result.content) <= MAX_RESULT_CHARS
