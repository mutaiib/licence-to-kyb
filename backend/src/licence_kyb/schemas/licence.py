"""Licence extraction schema: the contract between the extract step and everything after it.

Design rules (data-model.md, constitution Principle II):
- every value is wrapped in ``Field[T]``, list fields included, so the model can always say
  ``not_present`` or ``unclear`` instead of inventing a value;
- every closed list has an escape value (``other`` / ``unknown``);
- a value read from the document carries the exact text it came from;
- the schema guarantees shape and local invariants only; business rules live in ``rules/``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator
from pydantic import Field as PydField
from pydantic_core import PydanticCustomError

Status = Literal["present", "not_present", "unclear"]
Origin = Literal["read", "entered_by_reviewer"]
SelfConfidence = Literal["high", "medium", "low", "unknown"]

LegalForm = Literal[
    "llc",
    "llc_single_owner",
    "sole_establishment",
    "civil_company",
    "branch",
    "fze",
    "fzco",
    "fz_llc",
    "public_joint_stock",
    "private_joint_stock",
    "other",
]
LicenceCategory = Literal["commercial", "professional", "industrial", "tourism", "other"]
PersonRole = Literal["owner", "partner", "manager", "shareholder", "representative", "other"]
OWNER_ROLES: frozenset[str] = frozenset({"owner", "partner", "shareholder"})
"""Roles that hold shares in the business. A manager controls it but does not own it."""


def parse_licence_date(raw: Any) -> Any:
    """Accept DD/MM/YYYY (as printed on UAE licences), ISO dates and ``date`` objects."""
    if isinstance(raw, date) or raw is None:
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        raise PydanticCustomError("licence_date", "not a valid DD/MM/YYYY date")
    return raw


LicenceDate = Annotated[date, BeforeValidator(parse_licence_date)]
SharePct = Annotated[float, PydField(ge=0, le=100)]


class StrictModel(BaseModel):
    """A frozen model that refuses unknown keys. Every schema in this package uses it."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Field[T](StrictModel):
    """One extracted value with its evidence."""

    value: T | None
    status: Status
    origin: Origin = "read"
    evidence_quote: str | None
    page: Annotated[int, PydField(ge=1, le=5)] | None
    self_confidence: SelfConfidence

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.status != "present" and self.value is not None:
            raise PydanticCustomError(
                "absent_with_value", "a field that is not present has no value"
            )
        if self.status == "present" and self.value is None:
            raise PydanticCustomError("present_without_value", "a present field needs a value")
        if (
            self.status == "present"
            and self.origin == "read"
            and (not self.evidence_quote or self.page is None)
        ):
            raise PydanticCustomError(
                "missing_evidence", "a value read from the document needs its quote and page"
            )
        return self

    @property
    def is_present(self) -> bool:
        return self.status == "present"


class Activity(StrictModel):
    code: Field[str]
    description_en: Field[str]
    description_ar: Field[str]


class Person(StrictModel):
    name: Field[str]
    nationality: Field[str]
    role: Field[PersonRole]
    share_pct: Field[SharePct]


class TradeLicenceExtraction(StrictModel):
    licence_number: Field[str]
    unified_licence_number: Field[str]
    register_number: Field[str]
    chamber_number: Field[str]
    trade_name_en: Field[str]
    trade_name_ar: Field[str]
    legal_form: Field[LegalForm]
    licence_category: Field[LicenceCategory]
    licence_type: Field[str]
    issuing_authority: Field[str]
    establishment_date: Field[LicenceDate]
    issue_date: Field[LicenceDate]
    expiry_date: Field[LicenceDate]
    activities: Field[list[Activity]]
    people: Field[list[Person]]
    address: Field[str]

    @model_validator(mode="after")
    def _date_order(self) -> Self:
        issue, expiry, est = (
            self.issue_date.value,
            self.expiry_date.value,
            self.establishment_date.value,
        )
        if issue is not None and expiry is not None and issue >= expiry:
            raise PydanticCustomError(
                "date_order",
                "the issue date must be before the expiry date",
                {"fields": ["issue_date", "expiry_date"]},
            )
        if est is not None and issue is not None and est > issue:
            raise PydanticCustomError(
                "date_order",
                "the establishment date must not be after the issue date",
                {"fields": ["establishment_date", "issue_date"]},
            )
        return self


CRITICAL_FIELDS: tuple[str, ...] = (
    "licence_number",
    "trade_name_en",
    "trade_name_ar",
    "legal_form",
    "expiry_date",
    "people",
)


class CriticalFields(StrictModel):
    """The independent second reading of the critical fields only."""

    licence_number: Field[str]
    trade_name_en: Field[str]
    trade_name_ar: Field[str]
    legal_form: Field[LegalForm]
    expiry_date: Field[LicenceDate]
    people: Field[list[Person]]


DocType = Literal["trade_licence", "moa", "emirates_id", "passport", "other", "unclear"]
Authority = Literal["DET", "ADDED", "DMCC", "IFZA", "other", "unknown"]


class RouteResult(StrictModel):
    doc_type: DocType
    authority: Authority
    has_arabic: Literal["true", "false", "unknown"]
