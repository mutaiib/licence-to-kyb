"""Demo mode answers from labels, not a model, so its runs cost nothing (US5 visual check)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from licence_kyb.config import STEPS, load_model_profile
from licence_kyb.llm.client import ModelRequest
from licence_kyb.schemas.licence import RouteResult
from licence_kyb.testdata.answers import LabelDemoTransport


def test_a_demo_answer_costs_nothing(tmp_path: Path) -> None:
    labels = {"licence_number": "1234567"}
    (tmp_path / "case.json").write_text(json.dumps({"expected_values": labels}))
    request = ModelRequest(
        step="route",
        model="claude-opus-5-5",
        effort="low",
        max_tokens=100,
        system="s",
        messages=[{"role": "user", "content": [{"type": "text", "text": "Licence No 1234567"}]}],
        output_model=RouteResult,
    )

    response = LabelDemoTransport(tmp_path).send(request)

    assert response.cost_usd() == 0


def test_demo_mode_matches_a_whole_licence_number_not_part_of_a_longer_one(tmp_path: Path) -> None:
    """Found by the US6 eval: a 5-digit number inside a 7-digit one picked the wrong case."""
    (tmp_path / "a_short.json").write_text(
        json.dumps(
            {"expected_values": {"licence_number": "84099", "trade_name_en": "Wrong Case FZCO"}}
        )
    )
    (tmp_path / "b_right.json").write_text(
        json.dumps(
            {
                "expected_values": {
                    "licence_number": "CN-4840992",
                    "trade_name_en": "Right Case Est.",
                }
            }
        )
    )
    transport = LabelDemoTransport(tmp_path)
    text = "Licence No CN-4840992 Chamber No 12345"

    case = transport._case_for(
        ModelRequest(
            step="route",
            model="m",
            effort="low",
            max_tokens=10,
            system="s",
            messages=[{"role": "user", "content": [{"type": "text", "text": text}]}],
        )
    )

    assert case is not None
    assert case["expected_values"]["trade_name_en"] == "Right Case Est."


def test_a_demo_answer_reports_no_tokens_and_the_demo_profile_names_no_real_model(
    tmp_path: Path,
) -> None:
    """The trace must not show a Claude model and token counts for a run no model read."""
    labels = {"licence_number": "1234567"}
    (tmp_path / "case.json").write_text(json.dumps({"expected_values": labels}))
    profile = load_model_profile("demo")
    request = ModelRequest(
        step="route",
        model=profile.steps.route.model,
        effort="low",
        max_tokens=100,
        system="s",
        messages=[{"role": "user", "content": [{"type": "text", "text": "Licence No 1234567"}]}],
        output_model=RouteResult,
    )

    response = LabelDemoTransport(tmp_path).send(request)

    assert response.usage.billed_tokens == 0
    assert response.serving_model == request.model
    assert {getattr(profile.steps, s).model for s in STEPS} == {"demo-labels"}


@pytest.mark.parametrize(
    ("title", "doc_type"),
    [
        ("Memorandum of Association", "moa"),
        ("Resident Identity Card", "emirates_id"),
        ("PASSPORT", "passport"),
        ("Renewal Confirmation", "other"),
        ("", "unclear"),
    ],
)
def test_demo_mode_names_a_document_that_is_not_a_licence_by_its_title(
    tmp_path: Path, title: str, doc_type: str
) -> None:
    """With no licence number to match, the demo reads the title, as a model would."""
    request = ModelRequest(
        step="route",
        model="demo-labels",
        effort="low",
        max_tokens=100,
        system="s",
        messages=[{"role": "user", "content": [{"type": "text", "text": f"{title}\nPage 1"}]}],
        output_model=RouteResult,
    )

    response = LabelDemoTransport(tmp_path).send(request)

    assert response.parsed_as(RouteResult).doc_type == doc_type
