"""The KYB onboarding form: a draft before review, rebuilt after every decision (data-model.md)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class FormActivity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: str | None
    description: str | None


class FormPerson(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    nationality: str | None
    roles: tuple[str, ...]
    share_pct: float | None = None


class RequiredDocumentItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document: RequiredDocument
    for_person: str | None = None


class KYBOnboardingForm(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

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
