"""The synthetic catalogue: deterministic, complete, and correctly labelled (S10 AC1-AC2)."""

from __future__ import annotations

import io
import json
import random
import re
from pathlib import Path

import pdfplumber
import pytest

from licence_kyb.profiles import AUTHORITIES, load_profile
from licence_kyb.testdata.catalogue import GROUPS, build
from licence_kyb.testdata.spec import _wrong_number
from tests.builders import first_case

SMALL = tuple(
    g for g in GROUPS if g.name in {"clean", "injected", "registry_not_found", "out_of_scope"}
)
SMALL = tuple(
    type(g)(**{**g.__dict__, "count": 4}) if g.name in {"clean", "injected"} else g for g in SMALL
)


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
    case = first_case(cases, "clean")
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


def test_a_wrong_format_number_matches_no_authority_pattern() -> None:
    """Otherwise the router reads it as another authority's number (unknown_authority), and
    the wrong_number_format cases would never reach the number-format check."""
    patterns = [re.compile(load_profile(a).number_pattern) for a in AUTHORITIES]
    rng = random.Random(0)  # noqa: S311 - test data, not security
    for authority in AUTHORITIES:
        for _ in range(200):
            number = _wrong_number(authority, rng)
            assert not any(p.match(number) for p in patterns), (authority, number)


def test_each_group_is_split_evenly_between_calibration_and_test(
    built: tuple[Path, list[dict[str, object]]],
) -> None:
    """Every group appears in the test report; none is fitted on and never reported."""
    _, cases = built
    by_group: dict[str, list[str]] = {}
    for case in cases:
        by_group.setdefault(str(case["group"]), []).append(str(case["split"]))
    for group, splits in by_group.items():
        assert "test" in splits, group
        assert abs(splits.count("test") - splits.count("calibration")) <= 1, group


def test_an_injected_case_is_in_the_same_split_as_its_clean_twin(
    built: tuple[Path, list[dict[str, object]]],
) -> None:
    _, cases = built
    split_of = {c["case_id"]: c["split"] for c in cases}
    for case in cases:
        if case["twin_of"]:
            assert case["split"] == split_of[case["twin_of"]], case["case_id"]


def test_no_two_cases_share_a_document(built: tuple[Path, list[dict[str, object]]]) -> None:
    _, cases = built
    hashes = [c["document_sha256"] for c in cases]
    assert len(hashes) == len(set(hashes))
