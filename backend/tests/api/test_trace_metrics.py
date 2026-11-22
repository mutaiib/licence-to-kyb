"""Trace, run list and daily summary (US5; FR-032; contracts/http-api.md)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from licence_kyb.api.app import create_app
from licence_kyb.config import Settings
from licence_kyb.testdata.answers import ScriptedTransport
from licence_kyb.testdata.catalogue import GROUPS, build
from tests.builders import first_case, make_pipeline

PASSWORD = "correct horse battery staple"  # noqa: S105 - test-only reviewer account
BUDGET = 1_000_000


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict[str, Any]]]:
    root = tmp_path_factory.mktemp("cat")
    (root / "data").mkdir()
    groups = tuple(replace(g, count=1) for g in GROUPS if g.name in {"clean", "near_expiry"})
    return root, build(root, seed=17, groups=groups).cases


class Transports:
    """One scripted model per uploaded case: picks the case by its licence number."""

    def __init__(self, cases: list[dict[str, Any]], refusing: set[str]) -> None:
        self.by_number = {
            c["expected_values"]["licence_number"]: ScriptedTransport(
                c["expected_values"],
                faults={"refusal"} if c["case_id"] in refusing else set(),
            )
            for c in cases
        }

    def send(self, req: Any) -> Any:
        text = " ".join(str(m["content"]) for m in req.messages)
        number = next(n for n in self.by_number if n in text)
        return self.by_number[number].send(req)


def client_with(
    tmp_path: Path,
    catalogue: Any,
    *,
    refusing: set[str] | None = None,
    misread: dict[str, Any] | None = None,
) -> TestClient:
    root, cases = catalogue
    if misread:
        cases = [
            {**c, "expected_values": {**c["expected_values"], **misread.get(c["case_id"], {})}}
            for c in cases
        ]
    pipeline = make_pipeline(
        tmp_path / "var",
        Transports(cases, refusing or set()),  # type: ignore[arg-type]
        registry_path=root / "data" / "registry_mock.json",
        budget=BUDGET,
    )
    settings = Settings(
        reviewer_accounts={"reviewer1": PasswordHasher().hash(PASSWORD)},  # type: ignore[dict-item]
        session_secret="s" * 32,  # type: ignore[arg-type]
        cookie_secure=False,
    )
    client = TestClient(create_app(data_dir=tmp_path / "var", settings=settings, pipeline=pipeline))
    client.post("/api/session", json={"username": "reviewer1", "password": PASSWORD})
    return client


def upload(client: TestClient, root: Path, case: dict[str, Any]) -> str:
    response = client.post(
        "/api/runs",
        files={"file": ("l.pdf", (root / case["document"]).read_bytes(), "application/pdf")},
        data={"applicant_name": case["applicant_name"]},
        headers={"X-CSRF-Token": client.cookies["csrf"]},
    )
    run_id: str = response.json()["run_id"]
    return run_id


def personal_values(case: dict[str, Any]) -> list[str]:
    v = case["expected_values"]
    people = v.get("people") or []
    return [
        v["licence_number"],
        *(p["name"] for p in people),
        *(p["nationality"] for p in people if p.get("nationality")),
    ]


# ------------------------------------------------------------------ trace
def test_the_trace_lists_each_step_in_order_with_its_model_calls(
    tmp_path: Path, catalogue: Any
) -> None:
    root, cases = catalogue
    client = client_with(tmp_path, catalogue)
    run_id = upload(client, root, first_case(cases, "clean"))

    spans = client.get(f"/api/runs/{run_id}/trace").json()["spans"]

    steps = [s["name"] for s in spans if s["kind"] == "step"]
    assert steps.index("route") < steps.index("extract") < steps.index("validate")
    calls = [s for s in spans if s["kind"] == "model_call"]
    by_id = {s["span_id"]: s for s in spans}
    assert {c["name"] for c in calls} >= {"route", "extract_primary", "extract_secondary"}
    for call in calls:
        assert call["model"]
        assert call["cost_usd"] > 0
        assert by_id[call["parent_id"]]["kind"] == "step"


def test_the_resolver_s_model_and_tool_calls_are_traced_under_its_step(
    tmp_path: Path, catalogue: Any
) -> None:
    root, cases = catalogue
    case = first_case(cases, "near_expiry")
    truth = case["expected_values"]["expiry_date"]
    wrong = str(int(truth[:4]) + 2) + truth[4:]
    client = client_with(tmp_path, catalogue, misread={case["case_id"]: {"expiry_date": wrong}})
    run_id = upload(client, root, case)

    spans = client.get(f"/api/runs/{run_id}/trace").json()["spans"]

    resolve_steps = [s for s in spans if s["kind"] == "step" and s["name"] == "resolve"]
    assert resolve_steps
    under_resolve = {
        s["kind"] for s in spans if s["parent_id"] in {r["span_id"] for r in resolve_steps}
    }
    assert under_resolve == {"model_call", "tool_call"}


# ------------------------------------------------------------------ run list and summary
def test_the_run_list_shows_each_run_s_cost_and_duration(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    client = client_with(tmp_path, catalogue)
    upload(client, root, first_case(cases, "clean"))

    [run] = client.get("/api/runs").json()["runs"]

    assert run["cost_usd"] > 0
    assert run["duration_ms"] > 0


def test_the_summary_rates_match_the_day_s_runs(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    clean, near = first_case(cases, "clean"), first_case(cases, "near_expiry")
    client = client_with(tmp_path, catalogue, refusing={near["case_id"]})
    upload(client, root, clean)  # ready
    upload(client, root, near)  # the model refuses: review with processing_failed

    summary = client.get("/api/metrics/summary").json()

    assert summary["runs"] == 2
    assert summary["refusal_rate"] == pytest.approx(0.5)
    assert summary["review_rate"] == pytest.approx(0.5)
    assert summary["fallback_rate"] == 0
    assert summary["cost_usd"] > 0
    assert 0 < summary["budget_tokens_remaining"] < BUDGET


def test_no_response_shows_personal_data(tmp_path: Path, catalogue: Any) -> None:
    root, cases = catalogue
    case = first_case(cases, "near_expiry")
    client = client_with(tmp_path, catalogue)
    run_id = upload(client, root, case)

    bodies = " ".join(
        client.get(path).text
        for path in (f"/api/runs/{run_id}/trace", "/api/runs", "/api/metrics/summary")
    )

    for value in personal_values(case):
        assert value not in bodies
