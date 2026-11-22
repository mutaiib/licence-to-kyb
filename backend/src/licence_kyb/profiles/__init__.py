"""Authority profiles: per-authority facts that the rules and prompts depend on.

Each profile is a YAML file next to this module. ``number_pattern_source`` records how
firm the pattern is (``confirmed``, ``inferred``, ``demo_assumption`` or ``none``).
"""

from __future__ import annotations

import re
from functools import cache
from importlib import resources
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from licence_kyb.normalise import normalise_number
from licence_kyb.schemas.licence import LegalForm

AUTHORITIES: tuple[str, ...] = ("DET", "ADDED", "DMCC", "IFZA")


class AuthorityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    name_en: str
    number_pattern: str
    number_pattern_source: Literal["confirmed", "inferred", "demo_assumption", "none"]
    date_format: Literal["DD/MM/YYYY"]
    licence_number_labels: tuple[str, ...]
    licence_titles: tuple[str, ...]
    allowed_legal_forms: tuple[LegalForm, ...]
    arabic_name_required: bool
    has_qr: bool
    has_register: bool
    free_zone: bool
    tenancy_document: (
        Literal["tenancy_contract_ejari", "tenancy_contract_tawtheeq", "free_zone_lease"] | None
    )

    def matches_number(self, number: str) -> bool:
        return re.fullmatch(self.number_pattern, normalise_number(number)) is not None

    @property
    def number_regex(self) -> re.Pattern[str]:
        """The pattern without anchors, for searching inside OCR text."""
        return re.compile(self.number_pattern.removeprefix("^").removesuffix("$"))

    @property
    def numbers_in(self) -> re.Pattern[str]:
        """The pattern as a whole token: never part of a longer number or word."""
        return re.compile(rf"(?<![\w-])(?:{self.number_regex.pattern})(?![\w-])")


@cache
def load_profile(code: str) -> AuthorityProfile:
    name = code.lower() if code in AUTHORITIES else "generic"
    text = resources.files(__package__).joinpath(f"{name}.yaml").read_text(encoding="utf-8")
    return AuthorityProfile.model_validate(yaml.safe_load(text))


def authority_for_number(number: str) -> str | None:
    """The single known authority whose pattern matches ``number``, if exactly one does."""
    matches = [code for code in AUTHORITIES if load_profile(code).matches_number(number)]
    return matches[0] if len(matches) == 1 else None
