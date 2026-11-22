"""The synthetic catalogue: deterministic, complete, and correctly labelled (S10 AC1-AC2)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pdfplumber
import pytest

from licence_kyb.testdata.catalogue import GROUPS, build

SMALL = tuple(
    g for g in GROUPS if g.name in {"clean", "injected", "registry_not_found", "out_of_scope"}
)
SMALL = tuple(g if g.name != "clean" else type(g)(**{**g.__dict__, "count": 4}) for g in SMALL)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict[str, object]]]:
    root = tmp_path_factory.mktemp("cat")
    (root / "data").mkdir()
    return root, build(root, seed=7, groups=SMALL).cases


def test_the_same_seed_gives_identical_documents_and_labels(
    built: tuple[Path, list[dict[str, object]]], tmp_path: Path
) -> None:
    _, first = built
    (tmp_path / "data").mkdir()

    second = build(tmp_path, seed=7, groups=SMALL).cases

    assert first == second


def test_the_full_catalogue_has_every_group_with_its_count() -> None:
    counts = {g.name: g.count for g in GROUPS}

    assert sum(counts.values()) == 93  # plus 1 public licence = 94 labelled cases
    assert counts["clean"] == 24
    assert counts["injected"] == 6
    assert {"expired", "expired_uncertain", "out_of_scope", "unclear"} <= set(counts)


def test_a_licence_pdf_has_a_text_layer_with_its_number_and_the_synthetic_notice(
    built: tuple[Path, list[dict[str, object]]],
) -> None:
    root, cases = built
    case = next(c for c in cases if c["group"] == "clean")
    pdf = (root / str(case["document"])).read_bytes()

    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = doc.pages[0].extract_text() or ""

    expected = case["expected_values"]
    assert isinstance(expected, dict)
    assert str(expected["licence_number"]) in text
    assert "Synthetic test document" in text


def test_injected_twins_expect_the_same_values_and_route_as_their_clean_case(
    built: tuple[Path, list[dict[str, object]]],
) -> None:
    _, cases = built
    by_id = {c["case_id"]: c for c in cases}
    for case in (c for c in cases if c["group"] == "injected"):
        twin = by_id[str(case["twin_of"])]
        assert case["expected_values"] == twin["expected_values"]
        assert case["expected_route"] == twin["expected_route"]


def test_the_mock_registry_omits_not_found_cases_and_ifza(
    built: tuple[Path, list[dict[str, object]]],
) -> None:
    root, cases = built
    registry = json.loads((root / "data" / "registry_mock.json").read_text("utf-8"))

    assert "IFZA" not in registry
    for case in (c for c in cases if c["group"] == "registry_not_found"):
        values = case["expected_values"]
        assert isinstance(values, dict)
        assert values["licence_number"] not in registry.get(str(case["authority"]), {})


def test_every_case_has_a_split_and_a_mix_bucket(
    built: tuple[Path, list[dict[str, object]]],
) -> None:
    _, cases = built
    assert {c["split"] for c in cases} <= {"calibration", "test"}
    assert {c["mix_bucket"] for c in cases} <= {"clean", "scans_and_photos", "problem"}
