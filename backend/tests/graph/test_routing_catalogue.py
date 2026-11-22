"""US3 independent test, offline: one case from every licence group of the synthetic
catalogue runs through the whole pipeline and gets its expected route and reason codes.

The model is scripted from each case's labels, with the reading faults its case file
records, so this checks routing and rules, not the model's reading.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from licence_kyb.testdata.answers import READING_FAULTS, ScriptedTransport
from licence_kyb.testdata.catalogue import GROUPS, build
from tests.builders import make_pipeline


@pytest.fixture(scope="module")
def licence_cases(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict[str, Any]]]:
    root = tmp_path_factory.mktemp("catalogue")
    (root / "data").mkdir()
    groups = tuple(replace(g, count=1) for g in GROUPS)
    cases = [
        c
        for c in build(root, seed=11, groups=groups).cases
        if (c.get("expected_values") or {}).get("licence_number")
    ]
    return root, cases


def test_every_licence_group_gets_its_expected_route_and_reasons(
    tmp_path: Path, licence_cases: tuple[Path, list[dict[str, Any]]]
) -> None:
    root, cases = licence_cases
    wrong = []
    for case in cases:
        faults = set(case.get("faults", [])) & READING_FAULTS
        if case["expected_values"].get("people") is None:
            faults.add("owners_unclear")
        pipeline = make_pipeline(
            tmp_path / case["case_id"],
            ScriptedTransport(case["expected_values"], faults=faults),
            registry_path=root / "data" / "registry_mock.json",
        )
        run_id = pipeline.upload(
            (root / case["document"]).read_bytes(), applicant_name=case["applicant_name"]
        ).run_id
        assert run_id is not None
        state = pipeline.process(run_id)
        route = state["decision"]["route"]
        codes = {r["code"] for r in state["reasons"]}
        if route not in case["expected_route"] or not set(case["expected_reason_codes"]) <= codes:
            wrong.append(
                (
                    case["case_id"],
                    route,
                    sorted(codes),
                    case["expected_route"],
                    case["expected_reason_codes"],
                )
            )

    assert wrong == []
    assert len(cases) >= 15
