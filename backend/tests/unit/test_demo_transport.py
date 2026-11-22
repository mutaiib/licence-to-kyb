"""Demo mode: answers from the matching synthetic case; anything else reads as unclear."""

from __future__ import annotations

import json
from pathlib import Path

from licence_kyb.llm.client import ModelRequest
from licence_kyb.schemas.licence import RouteResult, TradeLicenceExtraction
from licence_kyb.testdata.answers import LabelDemoTransport

CASES = Path(__file__).resolve().parents[3] / "evals" / "cases" / "synthetic"


def request(step: str, text: str) -> ModelRequest:
    return ModelRequest(
        step=step,
        model="claude-opus-5-5",
        effort="low",
        max_tokens=100,
        system="",
        messages=[{"role": "user", "content": [{"type": "text", "text": text}]}],
    )


def test_a_document_containing_a_cases_licence_number_gets_that_cases_values() -> None:
    case = json.loads((CASES / "clean_001.json").read_text("utf-8"))
    number = case["expected_values"]["licence_number"]
    demo = LabelDemoTransport(CASES)

    route = RouteResult.model_validate(demo.send(request("route", f"Licence No {number}")).parsed)
    ex = TradeLicenceExtraction.model_validate(
        demo.send(request("extract_primary", f"x {number}")).parsed
    )

    assert route.doc_type == "trade_licence"
    assert ex.licence_number.value == number


def test_an_unknown_document_reads_as_unclear() -> None:
    demo = LabelDemoTransport(CASES)
    route = RouteResult.model_validate(demo.send(request("route", "nothing known")).parsed)
    assert route.doc_type == "unclear"
