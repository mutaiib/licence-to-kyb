"""What the extraction prompts give the model (domain review, round 3). These check coverage
and leaks of hints, never wording."""

from __future__ import annotations

from licence_kyb.config import StepModel
from licence_kyb.llm.prompts import load_prompt
from licence_kyb.nodes.extract import build_extract_request
from licence_kyb.profiles import load_profile
from licence_kyb.schemas.licence import CriticalFields, TradeLicenceExtraction

CFG = StepModel(model="m", effort="low", max_tokens=100)


def test_every_extracted_field_is_explained_in_the_primary_prompt() -> None:
    """A field the prompt never names invites a guess (a unified number in licence_number)."""
    prompt = load_prompt("extract_primary")

    missing = [name for name in TradeLicenceExtraction.model_fields if name not in prompt]

    assert missing == []


def test_the_second_reading_gets_the_same_guidance_on_people() -> None:
    """Both readings must map roles and shares the same way, or they disagree on people."""
    prompt = load_prompt("extract_secondary")

    assert "role" in prompt
    assert "share_pct" in prompt
    assert "people" in CriticalFields.model_fields


def test_no_request_lists_the_legal_forms_the_authority_allows() -> None:
    """A list of allowed forms invites the model to pick one of them instead of reading the
    printed form, which would hide legal_form_not_allowed."""
    profile = load_profile("DMCC")
    for step, output in (
        ("extract_primary", TradeLicenceExtraction),
        ("extract_secondary", CriticalFields),
    ):
        request = build_extract_request(
            step=step, output=output, pages_png=[], ocr_text="", profile=profile, cfg=CFG
        )

        assert "allowed_legal_forms" not in request.system
