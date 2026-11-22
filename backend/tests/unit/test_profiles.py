"""Authority profiles: each pattern accepts its own examples and rejects the others'."""

from __future__ import annotations

import pytest

from licence_kyb.profiles import AUTHORITIES, load_profile

EXAMPLES: dict[str, list[str]] = {
    "DET": ["1234567", "7654321"],
    "ADDED": ["CN-1002016", "CN-2680147"],
    "DMCC": ["DMCC-30894", "DMCC16914"],
    "IFZA": ["12345", "90817"],
}


@pytest.mark.parametrize("authority", ["DET", "ADDED", "DMCC", "IFZA", "generic"])
def test_every_profile_loads_with_the_fields_rules_depend_on(authority: str) -> None:
    profile = load_profile(authority)

    assert profile.code == authority
    assert profile.date_format == "DD/MM/YYYY"
    assert profile.licence_number_labels
    assert isinstance(profile.arabic_name_required, bool)
    assert isinstance(profile.has_register, bool)


@pytest.mark.parametrize(
    ("authority", "number"), [(a, n) for a, ns in EXAMPLES.items() for n in ns]
)
def test_pattern_accepts_its_own_examples(authority: str, number: str) -> None:
    assert load_profile(authority).matches_number(number)


@pytest.mark.parametrize(
    ("authority", "number"),
    [(a, n) for a in EXAMPLES for b, ns in EXAMPLES.items() if b != a for n in ns],
)
def test_pattern_rejects_other_authorities_examples(authority: str, number: str) -> None:
    assert not load_profile(authority).matches_number(number)


def test_added_pattern_rejects_a_short_or_unprefixed_number() -> None:
    added = load_profile("ADDED")

    assert not added.matches_number("CN-123456")
    assert not added.matches_number("1234567")


def test_ifza_has_no_register_lookup_in_the_demo() -> None:
    assert load_profile("IFZA").has_register is False
    assert {load_profile(a).has_register for a in ("DET", "ADDED", "DMCC")} == {True}


def test_free_zones_allow_free_zone_forms_and_not_mainland_llc() -> None:
    for code in ("DMCC", "IFZA"):
        profile = load_profile(code)
        assert "fze" in profile.allowed_legal_forms
        assert "llc" not in profile.allowed_legal_forms


def test_the_known_authorities_are_exactly_the_four_profiles() -> None:
    assert set(AUTHORITIES) == {"DET", "ADDED", "DMCC", "IFZA"}


def test_unknown_profile_name_falls_back_to_generic() -> None:
    assert load_profile("RAKEZ").code == "generic"
