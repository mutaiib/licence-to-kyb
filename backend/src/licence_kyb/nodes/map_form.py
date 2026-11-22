"""Draft KYB form from the extraction and the rule results (FR-031, data-model.md).

Deterministic and model-free. A value enters the form only when every rule on its source
field passed (or a person approved it, applied later in review). A flagged value is left
empty with the state ``needs_examination``.
"""

from __future__ import annotations

from typing import Any

from licence_kyb.profiles import load_profile
from licence_kyb.rules.base import normalise_name, present
from licence_kyb.schemas.kyb_form import (
    FieldState,
    FormActivity,
    FormPerson,
    FormValue,
    KYBOnboardingForm,
    RequiredDocumentItem,
)
from licence_kyb.schemas.licence import OWNER_ROLES, Person, TradeLicenceExtraction
from licence_kyb.schemas.results import RuleResult

UBO_THRESHOLD = 25.0
MOA_FORMS = frozenset({"llc", "llc_single_owner", "fzco", "fz_llc"})

# form field → source extraction field
SOURCES: dict[str, str] = {
    "legal_name_en": "trade_name_en",
    "legal_name_ar": "trade_name_ar",
    "legal_form": "legal_form",
    "licence_number": "licence_number",
    "issuing_authority": "issuing_authority",
    "issue_date": "issue_date",
    "expiry_date": "expiry_date",
    "activities": "activities",
    "registered_address": "address",
    "beneficial_owners": "people",
    "controllers": "people",
    "chamber_number": "chamber_number",
}


def _blocked_sources(results: list[RuleResult]) -> set[str]:
    return {f for r in results if r.counts_as_failed for f in r.fields}


def _person(p: Person) -> FormPerson:
    share = present(p.share_pct)
    return FormPerson(
        name=present(p.name) or "",
        nationality=present(p.nationality),
        roles=(present(p.role) or "other",),
        share_pct=share,
    )


def _activities(ex: TradeLicenceExtraction) -> tuple[FormActivity, ...]:
    return tuple(
        FormActivity(code=present(a.code), description=present(a.description_en))
        for a in present(ex.activities) or []
    )


def _merge(people: list[FormPerson]) -> list[FormPerson]:
    """Merge entries only when the normalised name AND nationality match."""
    merged: dict[tuple[str, str], FormPerson] = {}
    for p in people:
        key = (normalise_name(p.name), normalise_name(p.nationality or ""))
        if key in merged:
            prev = merged[key]
            roles = tuple(dict.fromkeys(prev.roles + p.roles))
            merged[key] = prev.model_copy(
                update={"roles": roles, "share_pct": prev.share_pct or p.share_pct}
            )
        else:
            merged[key] = p
    return list(merged.values())


def _owners_and_controllers(
    ex: TradeLicenceExtraction,
) -> tuple[tuple[FormPerson, ...], tuple[FormPerson, ...], bool]:
    people = present(ex.people) or []
    owners = [p for p in people if (present(p.role) or "") in OWNER_ROLES]
    shares_printed = any(present(p.share_pct) is not None for p in owners)
    ubos = [
        _person(p)
        for p in owners
        if (share := present(p.share_pct)) is not None and share >= UBO_THRESHOLD
    ]
    managers = [_person(p) for p in people if present(p.role) == "manager"]
    controllers = _merge(managers + ubos)
    return tuple(_merge(ubos)), tuple(controllers), shares_printed


def _required_documents(
    legal_form: str | None, authority: str, people: tuple[FormPerson, ...], shares_printed: bool
) -> tuple[RequiredDocumentItem, ...]:
    docs: list[RequiredDocumentItem] = []
    if legal_form in MOA_FORMS or not shares_printed:
        docs.append(RequiredDocumentItem(document="memorandum_of_association"))
    docs.extend(
        RequiredDocumentItem(document="identity_document", for_person=p.name) for p in people
    )
    tenancy = load_profile(authority).tenancy_document
    if tenancy:
        docs.append(RequiredDocumentItem(document=tenancy))
    if legal_form == "branch":
        docs.append(RequiredDocumentItem(document="parent_company_registration"))
    return tuple(docs)


def build_form(
    ex: TradeLicenceExtraction,
    results: list[RuleResult],
    *,
    authority: str,
    version: int,
    approved: frozenset[str] = frozenset(),
) -> KYBOnboardingForm:
    """``approved`` holds source fields a person approved, corrected or overrode."""
    blocked = _blocked_sources(results) - approved
    states: dict[str, FieldState] = {}

    def take(form_field: str, value: Any) -> Any:
        source = SOURCES[form_field]
        usable = getattr(ex, source).status == "present" and source not in blocked
        if source in approved:
            states[form_field] = "approved"
        else:
            states[form_field] = "passed" if usable else "needs_examination"
        return value if usable or source in approved else None

    ubos, controllers, shares_printed = _owners_and_controllers(ex)
    activities = _activities(ex)
    form = KYBOnboardingForm(
        version=version,
        legal_name_en=take("legal_name_en", present(ex.trade_name_en)),
        legal_name_ar=take("legal_name_ar", present(ex.trade_name_ar)),
        legal_form=take("legal_form", present(ex.legal_form)),
        licence_number=take("licence_number", present(ex.licence_number)),
        issuing_authority=take("issuing_authority", authority),
        issue_date=take("issue_date", present(ex.issue_date)),
        expiry_date=take("expiry_date", present(ex.expiry_date)),
        activities=take("activities", activities) or (),
        registered_address=take("registered_address", present(ex.address)),
        beneficial_owners=take("beneficial_owners", ubos) or (),
        controllers=take("controllers", controllers) or (),
        chamber_number=take("chamber_number", present(ex.chamber_number)),
        required_documents=_required_documents(
            present(ex.legal_form), authority, controllers, shares_printed
        ),
        field_states=states,
    )
    if not shares_printed and "people" not in approved:
        form = form.model_copy(
            update={"field_states": {**form.field_states, "beneficial_owners": "needs_examination"}}
        )
    return form


def read_values(ex: TradeLicenceExtraction) -> dict[str, FormValue]:
    """Each form field's value as read from the document, before any rule decides on it.

    The review page shows this value for a field that has no form value, because a reviewer
    must see what the licence says. Both owner fields list every person on the licence.
    """
    people = present(ex.people)
    everyone = None if people is None else tuple(_person(p) for p in people)
    activities = None if present(ex.activities) is None else _activities(ex)
    return {
        "legal_name_en": present(ex.trade_name_en),
        "legal_name_ar": present(ex.trade_name_ar),
        "legal_form": present(ex.legal_form),
        "licence_number": present(ex.licence_number),
        "issuing_authority": present(ex.issuing_authority),
        "issue_date": present(ex.issue_date),
        "expiry_date": present(ex.expiry_date),
        "activities": activities,
        "registered_address": present(ex.address),
        "beneficial_owners": everyone,
        "controllers": everyone,
        "chamber_number": present(ex.chamber_number),
    }
