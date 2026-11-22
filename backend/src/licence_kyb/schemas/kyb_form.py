"""The KYB onboarding form: a draft before review, rebuilt after every decision (data-model.md)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from licence_kyb.schemas.licence import StrictModel

FieldState = Literal[
    "passed", "flagged", "approved", "corrected", "overridden", "needs_examination"
]

RequiredDocument = Literal[
    "memorandum_of_association",
    "identity_document",
    "tenancy_contract_ejari",
    "tenancy_contract_tawtheeq",
    "free_zone_lease",
    "parent_company_registration",
]


class FormActivity(StrictModel):
    code: str | None
    description: str | None


class FormPerson(StrictModel):
    name: str
    nationality: str | None
    roles: tuple[str, ...]
    share_pct: float | None = None


class RequiredDocumentItem(StrictModel):
    document: RequiredDocument
    for_person: str | None = None


class KYBOnboardingForm(StrictModel):
    version: int = Field(ge=1)
    legal_name_en: str | None
    legal_name_ar: str | None
    legal_form: str | None
    licence_number: str | None
    issuing_authority: str | None
    issue_date: date | None
    expiry_date: date | None
    activities: tuple[FormActivity, ...]
    registered_address: str | None
    beneficial_owners: tuple[FormPerson, ...]
    controllers: tuple[FormPerson, ...]
    chamber_number: str | None
    required_documents: tuple[RequiredDocumentItem, ...]
    field_states: dict[str, FieldState]


FormValue = str | date | tuple[FormPerson, ...] | tuple[FormActivity, ...] | None
"""The value of one form field: text, a date, a list of people or a list of activities."""
