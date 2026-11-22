"""Test data builders: a valid clean DET licence, with any field overridden by name.

Builders keep tests short and make each test state only the values it is about.
"""

from __future__ import annotations

from typing import Any

from licence_kyb.schemas.licence import TradeLicenceExtraction


def field(
    value: Any,
    *,
    status: str | None = None,
    quote: str | None = None,
    origin: str = "read",
    page: int = 1,
) -> dict[str, Any]:
    status = status or ("present" if value is not None else "not_present")
    present = status == "present"
    if quote is None and present and origin == "read":
        quote = _quote(value)
    return {
        "value": value if present else None,
        "status": status,
        "origin": origin,
        "evidence_quote": quote if present else None,
        "page": page if present and origin == "read" else None,
        "self_confidence": "high" if present else "unknown",
    }


def _quote(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(_quote(v) for v in value)
    if isinstance(value, dict):
        return " ".join(
            _quote(v["value"]) for v in value.values() if isinstance(v, dict) and v.get("value")
        )
    text = str(value)
    if len(text) == 10 and text[4] == "-" and text[7] == "-":  # ISO date → printed DD/MM/YYYY
        return f"{text[8:10]}/{text[5:7]}/{text[0:4]}"
    return text


def person(
    name: str, *, nationality: str = "India", role: str = "owner", share: float | None = 100.0
) -> dict[str, Any]:
    return {
        "name": field(name),
        "nationality": field(nationality),
        "role": field(role),
        "share_pct": field(share),
    }


def activity(code: str, en: str) -> dict[str, Any]:
    return {"code": field(code), "description_en": field(en), "description_ar": field(None)}


def extraction(**overrides: Any) -> TradeLicenceExtraction:
    acts = overrides.pop("activities", [{"code": "6201.01", "en": "Computer Programming"}])
    data: dict[str, Any] = {
        "licence_number": field("1234567"),
        "unified_licence_number": field(None),
        "register_number": field(None),
        "chamber_number": field("393530"),
        "trade_name_en": field("Acme General Trading LLC"),
        "trade_name_ar": field("شركة الأفق للتجارة"),
        "legal_form": field("llc"),
        "licence_category": field("commercial"),
        "licence_type": field(None),
        "issuing_authority": field("DET"),
        "establishment_date": field("2020-01-15"),
        "issue_date": field("2026-03-01"),
        "expiry_date": field("2027-03-01"),
        "activities": field([activity(a["code"], a["en"]) for a in acts]),
        "people": field([person("Danielle Ellis", share=60.0), person("Amy Hawkins", share=40.0)]),
        "address": field("Office 657, Lara Forks, Dubai"),
    }
    data.update(overrides)
    return TradeLicenceExtraction.model_validate(data)
