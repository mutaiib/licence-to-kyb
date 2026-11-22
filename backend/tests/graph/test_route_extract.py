"""Route and extract through the graph, from the "Document identification and extraction"
table in test-cases.md. Synthetic documents only; scripted model responses (research R10a)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

from licence_kyb.clock import FixedClock
from licence_kyb.llm.client import DailyBudget, LLMClient
from licence_kyb.pipeline import Deps, Pipeline
from licence_kyb.registry import MockRegistry
from licence_kyb.security import Cipher
from licence_kyb.testdata.answers import ScriptedTransport
from licence_kyb.testdata.catalogue import GROUPS, build

WANTED = {
    "clean",
    "out_of_scope",
    "unclear",
    "arabic_name_missing",
    "injected",
    "labelled_number_other_doc",
}


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, dict[str, Any]]]:
    root = tmp_path_factory.mktemp("catalogue")
    (root / "data").mkdir()
    groups = tuple(replace(g, count=min(g.count, 4)) for g in GROUPS if g.name in WANTED)
    cases = build(root, seed=11, groups=groups).cases
    return root, {c["case_id"]: c for c in cases}


def run_case(
    root: Path,
    case: dict[str, Any],
    tmp_path: Path,
    transport: ScriptedTransport,
    budget: int = 1_000_000,
) -> tuple[dict[str, Any], Pipeline]:
    cipher = Cipher([Fernet.generate_key().decode()])
    deps = Deps(
        data_dir=tmp_path / "var",
        cipher=cipher,
        llm=LLMClient(transport, DailyBudget(limit_tokens=budget)),
        clock=FixedClock(),
        registry=MockRegistry(root / "data" / "registry_mock.json"),
    )
    pipeline = Pipeline(deps)
    upload = pipeline.upload(
        (root / case["document"]).read_bytes(), applicant_name=case["applicant_name"]
    )
    assert upload.reason_code is None
    assert upload.run_id is not None
    return pipeline.process(upload.run_id), pipeline


def codes(state: dict[str, Any]) -> set[str]:
    return {r["code"] for r in state.get("reasons", [])}


def values(state: dict[str, Any]) -> dict[str, Any]:
    ex = state["extraction"]
    return {
        k: ex[k]["value"] for k in ("licence_number", "trade_name_en", "legal_form", "expiry_date")
    }


def test_a_clean_det_licence_routes_ready_with_the_labelled_values(
    catalogue: Any, tmp_path: Path
) -> None:
    root, cases = catalogue
    case = next(c for c in cases.values() if c["group"] == "clean" and c["authority"] == "DET")

    state, _ = run_case(root, case, tmp_path, ScriptedTransport(case["expected_values"]))

    assert state["route"] == {"doc_type": "trade_licence", "authority": "DET"}
    assert state["decision"]["route"] == "ready", codes(state)
    exp = case["expected_values"]
    assert values(state) == {
        k: exp[k] for k in ("licence_number", "trade_name_en", "legal_form", "expiry_date")
    }


def test_a_clean_added_licence_has_a_cn_licence_number(catalogue: Any, tmp_path: Path) -> None:
    root, cases = catalogue
    case = next(c for c in cases.values() if c["group"] == "clean" and c["authority"] == "ADDED")

    state, _ = run_case(root, case, tmp_path, ScriptedTransport(case["expected_values"]))

    assert state["extraction"]["licence_number"]["value"].startswith("CN-")
    assert state["decision"]["route"] == "ready", codes(state)


@pytest.mark.parametrize(("doc_type", "index"), [("moa", 0), ("emirates_id", 1)])
def test_a_non_licence_without_a_licence_number_is_rejected_as_out_of_scope(
    catalogue: Any, tmp_path: Path, doc_type: str, index: int
) -> None:
    root, cases = catalogue
    case = cases[f"out_of_scope_{index + 1:03d}"]
    transport = ScriptedTransport(None, doc_type=doc_type, authority="unknown")

    state, _ = run_case(root, case, tmp_path, transport)

    assert state["decision"]["route"] == "reject"
    assert codes(state) == {"out_of_scope"}
    assert "extract_primary" not in transport.calls


def test_a_document_with_a_labelled_licence_number_is_never_rejected(
    catalogue: Any, tmp_path: Path
) -> None:
    root, cases = catalogue
    case = cases["labelled_number_other_doc_001"]

    state, _ = run_case(
        root, case, tmp_path, ScriptedTransport(None, doc_type="other", authority="unknown")
    )

    assert state["decision"]["route"] == "needs_review"
    assert "unclear_document" in codes(state)


def test_a_blank_page_goes_to_review_as_unclear(catalogue: Any, tmp_path: Path) -> None:
    root, cases = catalogue
    state, _ = run_case(
        root,
        cases["unclear_001"],
        tmp_path,
        ScriptedTransport(None, doc_type="unclear", authority="unknown"),
    )

    assert state["decision"]["route"] == "needs_review"
    assert codes(state) == {"unclear_document"}


def test_an_authority_that_contradicts_the_printed_number_becomes_unknown(
    catalogue: Any, tmp_path: Path
) -> None:
    root, cases = catalogue
    case = next(c for c in cases.values() if c["group"] == "clean" and c["authority"] == "ADDED")

    state, _ = run_case(
        root, case, tmp_path, ScriptedTransport(case["expected_values"], authority="DMCC")
    )

    assert state["route"]["authority"] == "unknown"
    assert "unknown_authority" in codes(state)
    assert state["decision"]["route"] == "needs_review"


def test_an_injected_document_has_the_same_outcome_as_its_clean_twin(
    catalogue: Any, tmp_path: Path
) -> None:
    root, cases = catalogue
    injected = next(c for c in cases.values() if c["group"] == "injected")
    twin = cases[injected["twin_of"]]

    a, _ = run_case(root, injected, tmp_path / "a", ScriptedTransport(injected["expected_values"]))
    b, _ = run_case(root, twin, tmp_path / "b", ScriptedTransport(twin["expected_values"]))

    assert a["decision"] == b["decision"]
    assert codes(a) == codes(b)
    assert values(a) == values(b)


def test_a_licence_without_an_arabic_name_reports_it_not_present(
    catalogue: Any, tmp_path: Path
) -> None:
    root, cases = catalogue
    case = next(c for c in cases.values() if c["group"] == "arabic_name_missing")

    state, _ = run_case(root, case, tmp_path, ScriptedTransport(case["expected_values"]))

    assert state["extraction"]["trade_name_ar"]["status"] == "not_present"
    assert "arabic_name_missing" in codes(state)


def test_an_unreadable_owners_table_is_unclear_and_flagged(catalogue: Any, tmp_path: Path) -> None:
    root, cases = catalogue
    case = next(c for c in cases.values() if c["group"] == "clean")

    state, _ = run_case(
        root, case, tmp_path, ScriptedTransport(case["expected_values"], faults={"people_unclear"})
    )

    assert state["extraction"]["people"]["status"] == "unclear"
    assert "owners_unclear" in codes(state)
    assert state["form"]["field_states"]["beneficial_owners"] == "needs_examination"


@pytest.mark.parametrize(
    ("fault", "code"),
    [
        ("malformed", "processing_failed"),
        ("refusal", "processing_failed"),
        ("fallback", "fallback_model"),
    ],
)
def test_model_failures_never_crash_and_never_route_ready(
    catalogue: Any, tmp_path: Path, fault: str, code: str
) -> None:
    root, cases = catalogue
    case = next(c for c in cases.values() if c["group"] == "clean")

    state, pipeline = run_case(
        root, case, tmp_path, ScriptedTransport(case["expected_values"], faults={fault})
    )

    assert state["decision"]["route"] == "needs_review"
    assert code in codes(state)
    run = pipeline.db.get_run(state["run_id"])
    assert run is not None
    assert run["status"] == "awaiting_review"


def test_one_malformed_reply_is_retried_and_then_succeeds(catalogue: Any, tmp_path: Path) -> None:
    root, cases = catalogue
    case = next(c for c in cases.values() if c["group"] == "clean")
    transport = ScriptedTransport(case["expected_values"], faults={"malformed_once"})

    state, _ = run_case(root, case, tmp_path, transport)

    assert transport.calls.count("extract_primary_retry") == 1
    assert "processing_failed" not in codes(state)


def test_an_exhausted_daily_budget_makes_no_model_call(catalogue: Any, tmp_path: Path) -> None:
    root, cases = catalogue
    case = next(c for c in cases.values() if c["group"] == "clean")
    transport = ScriptedTransport(case["expected_values"])

    state, _ = run_case(root, case, tmp_path, transport, budget=10)

    assert transport.calls == []
    assert codes(state) == {"budget_exhausted"}
    assert state["decision"]["route"] == "needs_review"


def test_checkpoints_on_disk_never_contain_document_values_in_plain_text(
    catalogue: Any, tmp_path: Path
) -> None:
    root, cases = catalogue
    case = next(c for c in cases.values() if c["group"] == "clean")

    run_case(root, case, tmp_path, ScriptedTransport(case["expected_values"]))

    raw = (tmp_path / "var" / "checkpoints.sqlite3").read_bytes()
    for secret in (
        case["expected_values"]["licence_number"],
        case["expected_values"]["people"][0]["name"],
    ):
        assert secret.encode() not in raw
    assert json.dumps(case["expected_values"]["address"]).encode() not in raw
