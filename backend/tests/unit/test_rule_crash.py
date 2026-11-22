"""A check that crashes can be overridden by a reviewer (traceability review, round 3).

Its result is "could not run", like a register that does not answer. If the reviewer could
not override it, a bug in one check would leave reject as the only action (FR-014, FR-024a).
"""

from __future__ import annotations

from typing import Any

import pytest

from licence_kyb import rules
from licence_kyb.rules import run_rules
from tests.unit.test_rules import context


def test_a_check_that_crashes_is_could_not_run_and_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(ctx: Any) -> Any:
        raise RuntimeError("a bug in the check")

    patched = tuple(
        (rule_id, fields, broken if rule_id == "qr" else rule)
        for rule_id, fields, rule in rules.RULES
    )
    monkeypatch.setattr(rules, "RULES", patched)

    [qr] = [r for r in run_rules(context()) if r.rule_id == "qr"]

    assert qr.outcome == "could_not_run"
    assert qr.overridable is True
