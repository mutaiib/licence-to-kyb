"""Business rules in plain code (constitution Principle IV; spec FR-012 to FR-014).

``run_rules`` runs every rule and never raises: a rule that fails unexpectedly becomes a
``could_not_run`` result for its fields, and every other rule still runs.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from licence_kyb.config import APPLICANT_NAME_THRESHOLD
from licence_kyb.profiles import AuthorityProfile, load_profile
from licence_kyb.rules.activity import activity_rule
from licence_kyb.rules.applicant import applicant_rule
from licence_kyb.rules.arabic_name import arabic_name_rule
from licence_kyb.rules.base import RegistryResult
from licence_kyb.rules.dates import date_order_rule
from licence_kyb.rules.expiry import expiry_rule
from licence_kyb.rules.grounding import evidence_rule
from licence_kyb.rules.legal_form import legal_form_rule
from licence_kyb.rules.number_format import number_format_rule
from licence_kyb.rules.ownership import owners_rule, shares_total_rule, sole_owner_rule, ubo_rule
from licence_kyb.rules.qr import qr_rule
from licence_kyb.rules.registry import registry_rule
from licence_kyb.rules.required import required_fields_rule
from licence_kyb.schemas.licence import TradeLicenceExtraction
from licence_kyb.schemas.results import RuleResult

__all__ = ["RegistryLookup", "RegistryResult", "RuleContext", "run_rules"]

log = logging.getLogger(__name__)

RegistryLookup = Callable[[str, str], RegistryResult]


@dataclass(frozen=True)
class RuleContext:
    extraction: TradeLicenceExtraction
    authority: str
    today: date
    ocr_text: str | None
    qr_payload: str | None
    registry: RegistryLookup
    applicant_name: str
    applicant_threshold: float = APPLICANT_NAME_THRESHOLD
    secondary_expiry: date | None = None
    """The expiry date as the second, independent reading read it (None: not read)."""
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def profile(self) -> AuthorityProfile:
        return load_profile(self.authority)


Rule = Callable[[RuleContext], list[RuleResult]]

RULES: tuple[tuple[str, tuple[str, ...], Rule], ...] = (
    ("required", (), required_fields_rule),
    ("expiry", ("expiry_date",), expiry_rule),
    ("number_format", ("licence_number",), number_format_rule),
    ("date_order", ("issue_date", "expiry_date"), date_order_rule),
    ("shares_total", ("people",), shares_total_rule),
    ("sole_owner_count", ("legal_form", "people"), sole_owner_rule),
    ("ubo", ("people",), ubo_rule),
    ("owners", ("people",), owners_rule),
    ("legal_form", ("legal_form",), legal_form_rule),
    ("arabic_name", ("trade_name_ar",), arabic_name_rule),
    ("high_risk_activity", ("activities",), activity_rule),
    ("evidence", (), evidence_rule),
    ("qr", ("licence_number",), qr_rule),
    ("registry", ("licence_number", "expiry_date"), registry_rule),
    ("applicant_name", ("trade_name_en",), applicant_rule),
)


def run_rules(ctx: RuleContext) -> list[RuleResult]:
    results: list[RuleResult] = []
    for rule_id, fields, rule in RULES:
        try:
            results.extend(rule(ctx))
        except Exception:  # one rule must never stop validation (S4 AC4)
            log.exception("rule could not run", extra={"rule_id": rule_id})
            results.append(
                RuleResult(
                    rule_id=rule_id,
                    fields=fields,
                    severity="block",
                    outcome="could_not_run",
                    reason_code="other",
                )
            )
    return results
