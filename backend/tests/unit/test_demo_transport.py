"""Demo mode answers from labels, not a model, so its runs cost nothing (US5 visual check)."""

from __future__ import annotations

import json
from pathlib import Path

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
