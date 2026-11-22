"""Versioned prompt files. Every model-call span records the prompt hash."""

from __future__ import annotations

import hashlib
from functools import cache
from importlib import resources


@cache
def load_prompt(name: str) -> str:
    return resources.files(__package__).joinpath(f"{name}.md").read_text(encoding="utf-8")


def prompt_hash(name: str) -> str:
    return hashlib.sha256(load_prompt(name).encode()).hexdigest()[:16]
