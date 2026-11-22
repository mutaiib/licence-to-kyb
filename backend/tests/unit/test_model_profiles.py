"""Model profiles (FR-044, ADR-004): MODEL_PROFILE picks the provider and models by
configuration only."""

from __future__ import annotations

import pytest

from licence_kyb.config import STEPS, load_model_profile


@pytest.mark.parametrize("name", ["anthropic", "local"])
def test_every_profile_names_a_model_for_every_step(name: str) -> None:
    profile = load_model_profile(name)

    assert {step for step in STEPS if getattr(profile.steps, step).model} == set(STEPS)


def test_the_default_profile_is_claude_through_the_anthropic_api() -> None:
    profile = load_model_profile(None)

    assert profile.provider == "anthropic"
    assert profile.steps.extract_primary.model.startswith("claude-")


def test_the_local_profile_costs_nothing_and_has_a_longer_deadline() -> None:
    local, default = load_model_profile("local"), load_model_profile("anthropic")

    assert local.provider == "openai_compatible"
    assert local.price_per_mtok.input == local.price_per_mtok.output == 0
    assert local.deadline_seconds is not None
    assert default.deadline_seconds is None or local.deadline_seconds > default.deadline_seconds


def test_an_unknown_profile_fails_with_a_message_that_names_the_valid_ones() -> None:
    with pytest.raises(ValueError, match="anthropic") as err:
        load_model_profile("no-such-profile")

    assert "local" in str(err.value)
