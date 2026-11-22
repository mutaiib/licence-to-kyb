"""Synthetic twins of approved corrections (US6, T091): same fault and layout, none of the
correction's personal values."""

from __future__ import annotations

import json
from pathlib import Path

from evals.twins import make_twin


def correction() -> dict[str, object]:
    return {
        "capture_key": "c-1",
        "field": "expiry_date",
        "fault_group": "evidence_mismatch",
        "authority": "DET",
        "read_value": "2028-06-11",
        "corrected_value": "2026-06-11",
        "people": ["Ahmed Al Mansoori"],
        "licence_number": "7828167",
        "trade_name_en": "Fuller Services LLC",
    }


def test_a_twin_keeps_the_fault_and_layout_but_none_of_the_personal_values(
    tmp_path: Path,
) -> None:
    source = correction()

    twin = make_twin(source, out_dir=tmp_path, seed=7)

    assert twin["group"] == "twin"
    assert twin["fault_group"] == "evidence_mismatch"
    assert twin["authority"] == "DET"
    assert twin["corrected_field"] == "expiry_date"
    text = json.dumps(twin, ensure_ascii=False) + (tmp_path / twin["document"]).read_text("latin-1")
    for value in ("Ahmed Al Mansoori", "7828167", "Fuller Services LLC", "2028-06-11"):
        assert value not in text
    assert (tmp_path / twin["document"]).exists()


def test_the_same_correction_and_seed_give_the_same_twin(tmp_path: Path) -> None:
    first = make_twin(correction(), out_dir=tmp_path / "a", seed=7)
    second = make_twin(correction(), out_dir=tmp_path / "b", seed=7)

    assert first["expected_values"] == second["expected_values"]
