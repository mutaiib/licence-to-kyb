"""Re-reading failed values (US4): the "Re-reading failed values" table in
specs/001-licence-to-kyb/test-cases.md. The model's tool loop is scripted (research R10a);
everything else (OCR, rules, tools, graph) is real."""

from __future__ import annotations

import itertools
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from licence_kyb.llm.client import ModelRequest, ModelResponse, Usage
from licence_kyb.registry import MockRegistry
from licence_kyb.testdata.answers import ScriptedTransport, dmy
from licence_kyb.testdata.catalogue import GROUPS, build
from tests.builders import first_case, make_pipeline

_ids = itertools.count()


def tool(name: str, **arguments: Any) -> dict[str, Any]:
    return {"type": "tool_use", "id": f"t{next(_ids)}", "name": name, "input": arguments}


def finish() -> dict[str, Any]:
    return tool("finish", summary="done")


class ToolLoopTransport(ScriptedTransport):
    """Reads the document from its labels; answers the resolver with scripted turns."""

    def __init__(
        self,
        labels: dict[str, Any],
        turns: list[list[dict[str, Any]]],
        *,
        tokens_per_turn: int = 2_000,
        endless: list[dict[str, Any]] | None = None,
    ):
        super().__init__(labels)
        self.turns = list(turns)
        self.endless = endless
        self.tokens_per_turn = tokens_per_turn
        self.resolve_calls = 0

    def send(self, req: ModelRequest) -> ModelResponse:
        if req.step != "resolve":
            return super().send(req)
        self.resolve_calls += 1
        blocks = self.turns.pop(0) if self.turns else self.endless or [finish()]
        blocks = [{**b, "id": f"t{next(_ids)}"} for b in blocks]
        return ModelResponse(
            content=blocks,
            parsed=None,
            stop_reason="tool_use",
            serving_model=req.model,
            usage=Usage(
                input_tokens=self.tokens_per_turn // 2, output_tokens=self.tokens_per_turn // 2
            ),
        )


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict[str, Any]]]:
    root = tmp_path_factory.mktemp("cat")
    (root / "data").mkdir()
    groups = tuple(
        replace(g, count=1)
        for g in GROUPS
        if g.name in {"clean", "near_expiry", "expired_uncertain"}
    )
    cases = build(root, seed=13, groups=groups).cases
    return root, cases


def run(
    tmp_path: Path,
    catalogue: Any,
    group: str,
    transport_for: Any,
    *,
    misread: dict[str, str] | None = None,
    registry_down: bool = False,
) -> tuple[Any, Any]:
    root, cases = catalogue
    case = first_case(cases, group)
    labels = {**case["expected_values"], **(misread or {})}
    transport = transport_for(labels, case)
    pipeline = make_pipeline(
        tmp_path / "var", transport, registry_path=root / "data" / "registry_mock.json"
    )
    if registry_down:
        pipeline.deps.registry = MockRegistry(
            root / "data" / "registry_mock.json", unavailable=True
        )
    run_id = pipeline.upload(
        (root / case["document"]).read_bytes(), applicant_name=case["applicant_name"]
    ).run_id
    return pipeline.process(run_id), transport


def wrong_year(iso: str) -> str:
    return str(int(iso[:4]) + 2) + iso[4:]


def rules_on(state: dict[str, Any], field: str) -> dict[str, str]:
    return {r["rule_id"]: r["outcome"] for r in state["rule_results"] if field in r["fields"]}


# ------------------------------------------------------------------ the table
def fix_expiry(labels: dict[str, Any], case: dict[str, Any]) -> ToolLoopTransport:
    """A resolver that reads the OCR text, proposes the true expiry date, and finishes."""
    truth = case["expected_values"]["expiry_date"]
    return ToolLoopTransport(
        labels,
        [
            [tool("licence_ocr_region", page=1, region="full_page")],
            [
                tool(
                    "propose_fix",
                    field="expiry_date",
                    new_value=dmy(truth),
                    evidence_quote=f"Expiry Date {dmy(truth)}",
                    self_confidence="high",
                    rationale="The OCR text shows a different year.",
                )
            ],
            [finish()],
        ],
    )


def test_a_misread_expiry_is_re_read_and_the_corrected_value_is_kept(
    tmp_path: Path, catalogue: Any
) -> None:
    transport = fix_expiry
    truth = first_case(catalogue[1], "near_expiry")["expected_values"]["expiry_date"]
    state, _ = run(
        tmp_path, catalogue, "near_expiry", transport, misread={"expiry_date": wrong_year(truth)}
    )

    assert state["extraction"]["expiry_date"]["value"] == truth
    assert rules_on(state, "expiry_date")["evidence"] == "passed"
    assert [(p["field"], p["accepted"]) for p in state["proposals"]] == [("expiry_date", True)]


def test_the_two_readings_no_longer_count_as_agreeing_on_a_value_the_resolver_changed(
    tmp_path: Path, catalogue: Any
) -> None:
    """Both readings agreed on the misread date. The resolver's new value was seen by
    neither, so their agreement must not raise its confidence or corroborate it."""
    truth = first_case(catalogue[1], "near_expiry")["expected_values"]["expiry_date"]
    state, _ = run(
        tmp_path, catalogue, "near_expiry", fix_expiry, misread={"expiry_date": wrong_year(truth)}
    )

    assert state["extraction"]["expiry_date"]["value"] == truth
    assert state["agreement"]["expiry_date"] is False
    assert state["confidence"]["expiry_date"]["signals"]["agreement"] == 0.0


def test_a_proposal_for_a_field_that_passed_changes_nothing(tmp_path: Path, catalogue: Any) -> None:
    def transport(labels: dict[str, Any], case: dict[str, Any]) -> ToolLoopTransport:
        return ToolLoopTransport(
            labels,
            [
                [
                    tool(
                        "propose_fix",
                        field="trade_name_en",
                        new_value="Other Name LLC",
                        evidence_quote="Other Name LLC",
                        self_confidence="high",
                        rationale="x",
                    )
                ],
                [finish()],
            ],
        )

    truth = first_case(catalogue[1], "near_expiry")["expected_values"]
    state, _ = run(
        tmp_path,
        catalogue,
        "near_expiry",
        transport,
        misread={"expiry_date": wrong_year(truth["expiry_date"])},
    )

    assert state["extraction"]["trade_name_en"]["value"] == truth["trade_name_en"]
    assert not any(p["field"] == "trade_name_en" for p in state.get("proposals", []))


def test_a_proposal_that_breaks_a_rule_keeps_the_original_and_the_flag(
    tmp_path: Path, catalogue: Any
) -> None:
    misread_number = "12A4567"

    def transport(labels: dict[str, Any], case: dict[str, Any]) -> ToolLoopTransport:
        return ToolLoopTransport(
            labels,
            [
                [
                    tool(
                        "propose_fix",
                        field="licence_number",
                        new_value="CN-12345",
                        evidence_quote="CN-12345",
                        self_confidence="low",
                        rationale="guess",
                    )
                ],
                [finish()],
            ],
        )

    state, _ = run(
        tmp_path, catalogue, "clean", transport, misread={"licence_number": misread_number}
    )

    assert state["extraction"]["licence_number"]["value"] == misread_number
    assert "failed" in rules_on(state, "licence_number").values()
    assert state["decision"]["route"] == "needs_review"


def test_a_register_that_never_answers_still_reaches_a_route_that_is_not_ready(
    tmp_path: Path, catalogue: Any
) -> None:
    def transport(labels: dict[str, Any], case: dict[str, Any]) -> ToolLoopTransport:
        return ToolLoopTransport(
            labels,
            [
                [
                    tool(
                        "licence_lookup_registry",
                        licence_number=labels["licence_number"],
                        authority=case["authority"],
                    )
                ],
                [finish()],
            ],
        )

    truth = first_case(catalogue[1], "near_expiry")["expected_values"]["expiry_date"]
    state, _ = run(
        tmp_path,
        catalogue,
        "near_expiry",
        transport,
        registry_down=True,
        misread={"expiry_date": wrong_year(truth)},
    )

    assert state["decision"]["route"] in ("needs_review", "reject")
    assert state["decision"]["route"] != "ready"


def test_a_model_that_never_finishes_stops_at_the_turn_limit(
    tmp_path: Path, catalogue: Any
) -> None:
    holder: dict[str, ToolLoopTransport] = {}

    def transport(labels: dict[str, Any], case: dict[str, Any]) -> ToolLoopTransport:
        holder["t"] = ToolLoopTransport(labels, [], endless=[tool("licence_get_validation_report")])
        return holder["t"]

    truth = first_case(catalogue[1], "near_expiry")["expected_values"]["expiry_date"]
    state, _ = run(
        tmp_path, catalogue, "near_expiry", transport, misread={"expiry_date": wrong_year(truth)}
    )

    assert holder["t"].resolve_calls == 6
    assert "resolver_budget" in {r["code"] for r in state["reasons"]}
    assert state["decision"]["route"] == "needs_review"


def test_a_model_that_uses_too_many_tokens_stops_at_the_token_limit(
    tmp_path: Path, catalogue: Any
) -> None:
    holder: dict[str, ToolLoopTransport] = {}

    def transport(labels: dict[str, Any], case: dict[str, Any]) -> ToolLoopTransport:
        holder["t"] = ToolLoopTransport(
            labels, [], tokens_per_turn=25_000, endless=[tool("licence_get_validation_report")]
        )
        return holder["t"]

    truth = first_case(catalogue[1], "near_expiry")["expected_values"]["expiry_date"]
    state, _ = run(
        tmp_path, catalogue, "near_expiry", transport, misread={"expiry_date": wrong_year(truth)}
    )

    assert holder["t"].resolve_calls == 2
    assert "resolver_budget" in {r["code"] for r in state["reasons"]}


def test_vision_re_reads_count_against_the_resolver_token_limit(
    tmp_path: Path, catalogue: Any
) -> None:
    """Each re-read is a model call that costs tokens. They must count against the limit,
    or a model could re-read region after region past the 40k token budget."""
    holder: dict[str, Any] = {}

    class VisionTransport(ToolLoopTransport):
        vision_calls = 0

        def send(self, req: ModelRequest) -> ModelResponse:
            if req.step != "reread_vision":
                return super().send(req)
            self.vision_calls += 1
            return ModelResponse(
                content=[{"type": "text", "text": "Expiry Date"}],
                parsed=None,
                stop_reason="end_turn",
                serving_model=req.model,
                usage=Usage(input_tokens=20_000, output_tokens=5_000),
            )

    regions = ["top_left", "top_right", "middle", "bottom_left", "bottom_right", "full_page"]

    def transport(labels: dict[str, Any], case: dict[str, Any]) -> ToolLoopTransport:
        turns = [
            [tool("licence_reread_region", page=1, field="expiry_date", region=r)] for r in regions
        ]
        holder["t"] = VisionTransport(labels, turns, tokens_per_turn=1_000)
        return holder["t"]

    truth = first_case(catalogue[1], "near_expiry")["expected_values"]["expiry_date"]
    state, _ = run(
        tmp_path, catalogue, "near_expiry", transport, misread={"expiry_date": wrong_year(truth)}
    )

    assert holder["t"].vision_calls == 2  # 2 x 25k re-read tokens reach the 40k hard limit
    assert "resolver_budget" in {r["code"] for r in state["reasons"]}


def test_no_re_readable_failure_means_no_resolver_call(tmp_path: Path, catalogue: Any) -> None:
    holder: dict[str, ToolLoopTransport] = {}

    def transport(labels: dict[str, Any], case: dict[str, Any]) -> ToolLoopTransport:
        holder["t"] = ToolLoopTransport(labels, [])
        return holder["t"]

    state, _ = run(tmp_path, catalogue, "clean", transport)

    assert holder["t"].resolve_calls == 0
    assert not state.get("proposals")
    assert state["decision"]["route"] == "ready"


def test_text_asking_to_submit_cannot_make_the_resolver_submit(
    tmp_path: Path, catalogue: Any
) -> None:
    def transport(labels: dict[str, Any], case: dict[str, Any]) -> ToolLoopTransport:
        return ToolLoopTransport(labels, [[tool("submit_form", approve=True)], [finish()]])

    truth = first_case(catalogue[1], "near_expiry")["expected_values"]["expiry_date"]
    state, _ = run(
        tmp_path, catalogue, "near_expiry", transport, misread={"expiry_date": wrong_year(truth)}
    )

    assert state["status"] != "submitted"
    assert state.get("submission") is None


def test_an_uncertain_expiry_is_re_read_but_an_expired_date_is_never_accepted(
    tmp_path: Path, catalogue: Any
) -> None:
    """Found in the US4 visual check: the resolver skipped expiry_uncertain, because the
    corroboration rule ran after validation. The scripted resolver proposes the true date,
    which is expired, so the checks must refuse it and the run stays in review."""

    def transport(labels: dict[str, Any], case: dict[str, Any]) -> ScriptedTransport:
        return ScriptedTransport(labels, faults={"expired_uncertain"})

    state, _ = run(tmp_path, catalogue, "expired_uncertain", transport)

    assert [(p["field"], p["accepted"]) for p in state["proposals"]] == [("expiry_date", False)]
    assert state["decision"]["route"] == "needs_review"
    assert "expiry_uncertain" in {r["code"] for r in state["reasons"]}


def test_the_resolver_is_told_the_licence_number_and_authority(
    tmp_path: Path, catalogue: Any
) -> None:
    """The model needs both to call licence_lookup_registry."""
    holder: dict[str, Any] = {}

    class Recording(ToolLoopTransport):
        def send(self, req: ModelRequest) -> ModelResponse:
            if req.step == "resolve":
                holder["brief"] = req.messages[0]["content"][0]["text"]
            return super().send(req)

    def transport(labels: dict[str, Any], case: dict[str, Any]) -> ToolLoopTransport:
        holder["case"] = case
        return Recording(labels, [[finish()]])

    truth = first_case(catalogue[1], "near_expiry")["expected_values"]["expiry_date"]
    run(tmp_path, catalogue, "near_expiry", transport, misread={"expiry_date": wrong_year(truth)})

    assert holder["case"]["expected_values"]["licence_number"] in holder["brief"]
    assert holder["case"]["authority"] in holder["brief"]


def test_an_unexpected_error_in_the_resolver_does_not_end_the_run(
    tmp_path: Path, catalogue: Any
) -> None:
    class Broken(ToolLoopTransport):
        def send(self, req: ModelRequest) -> ModelResponse:
            if req.step == "resolve":
                raise ValueError("a bug in a model client")
            return super().send(req)

    truth = first_case(catalogue[1], "near_expiry")["expected_values"]["expiry_date"]
    state, _ = run(
        tmp_path,
        catalogue,
        "near_expiry",
        lambda labels, case: Broken(labels, []),
        misread={"expiry_date": wrong_year(truth)},
    )

    assert state["decision"]["route"] == "needs_review"
    assert "processing_failed" not in {r["code"] for r in state["reasons"]}
