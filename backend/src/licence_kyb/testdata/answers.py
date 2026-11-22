"""Model responses written from a case's labels (research R10a).

Used by offline graph tests (``ScriptedTransport``) and by the local demo mode
(``LabelDemoTransport``), which lets the app run end to end without a model API key.
Neither is a model: they return the labelled answer for a synthetic document.

It answers like a model that reads the document correctly, unless a fault asks otherwise.
Faults: ``malformed`` (invalid twice), ``malformed_once`` (invalid, then valid),
``refusal``, ``fallback`` and ``owners_unclear``.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from licence_kyb.llm.client import ModelRequest, ModelResponse, Usage
from licence_kyb.schemas.licence import CRITICAL_FIELDS
from licence_kyb.testdata.render import AUTHORITY_TITLE, LABELS
from licence_kyb.testdata.spec import LEGAL_FORMS

USAGE = Usage(input_tokens=9000, output_tokens=2500, thinking_tokens=1200, cache_read_tokens=3000)
FALLBACK_MODEL = "claude-sonnet-5-5"  # the model a server-side fallback serves
FORM_LABEL = {code: en for forms in LEGAL_FORMS.values() for code, en, _ar in forms}


def read_field(value: Any, quote: str) -> dict[str, Any]:
    """A field the model read from the document, with its quote."""
    return {
        "value": value,
        "status": "present",
        "origin": "read",
        "evidence_quote": quote,
        "page": 1,
        "self_confidence": "high",
    }


def missing_field(status: str = "not_present") -> dict[str, Any]:
    """A field the model did not find (``not_present``) or could not read (``unclear``)."""
    return {
        "value": None,
        "status": status,
        "origin": "read",
        "evidence_quote": None,
        "page": None,
        "self_confidence": "unknown",
    }


def _misread_year(field: dict[str, Any]) -> dict[str, Any]:
    if field.get("value") is None:
        return field
    value = str(field["value"])
    return {**field, "value": str(int(value[:4]) + 1) + value[4:]}


def dmy(iso: str) -> str:
    """An ISO date as the licence prints it: DD/MM/YYYY."""
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def extraction_from_labels(v: dict[str, Any], faults: set[str]) -> dict[str, Any]:
    def labelled(key: str, value: str, printed: str | None = None) -> dict[str, Any]:
        return read_field(value, f"{LABELS[key][0]} {printed or value}")

    people: dict[str, Any]
    if v["people"] is None or "owners_unclear" in faults:
        people = missing_field("unclear")
    else:
        people = read_field(
            [
                {
                    "name": read_field(p["name"], p["name"]),
                    "nationality": read_field(p["nationality"], p["nationality"]),
                    "role": read_field(p["role"], p["role"].title()),
                    "share_pct": read_field(p["share_pct"], f"{p['share_pct']:g}%")
                    if p["share_pct"] is not None
                    else missing_field(),
                }
                for p in v["people"]
            ],
            " ".join(p["name"] for p in v["people"]),
        )
    return {
        "licence_number": labelled("licence_number", v["licence_number"]),
        "unified_licence_number": missing_field(),
        "register_number": missing_field(),
        "chamber_number": labelled("chamber_number", v["chamber_number"]),
        "trade_name_en": labelled("trade_name_en", v["trade_name_en"]),
        "trade_name_ar": read_field(v["trade_name_ar"], v["trade_name_ar"])
        if v.get("trade_name_ar")
        else missing_field(),
        "legal_form": read_field(v["legal_form"], FORM_LABEL.get(v["legal_form"], v["legal_form"])),
        "licence_category": missing_field(),
        "licence_type": missing_field(),
        "issuing_authority": read_field(
            v["issuing_authority"], AUTHORITY_TITLE[v["issuing_authority"]][0]
        ),
        "establishment_date": labelled(
            "establishment_date", v["establishment_date"], dmy(v["establishment_date"])
        ),
        "issue_date": labelled("issue_date", v["issue_date"], dmy(v["issue_date"])),
        "expiry_date": labelled("expiry_date", v["expiry_date"], dmy(v["expiry_date"])),
        "activities": read_field(
            [
                {
                    "code": read_field(a["code"], a["code"]),
                    "description_en": read_field(a["description_en"], a["description_en"]),
                    "description_ar": missing_field(),
                }
                for a in v["activities"]
            ],
            " ".join(f"{a['code']} {a['description_en']}" for a in v["activities"]),
        ),
        "people": people,
        "address": labelled("address", v["address"]),
    }


READING_FAULTS = frozenset({"expired_uncertain"})
"""Document faults that make a real model's readings differ (the rest are in the pixels)."""


class ScriptedTransport:
    def __init__(
        self,
        labels: dict[str, Any] | None,
        *,
        doc_type: str = "trade_licence",
        authority: str | None = None,
        faults: set[str] | None = None,
    ) -> None:
        self.labels = labels
        self.doc_type = doc_type
        self.authority = authority or (labels or {}).get("issuing_authority", "unknown")
        self.faults = faults or set()
        self.calls: list[str] = []

    def send(self, req: ModelRequest) -> ModelResponse:
        self.calls.append(req.step)
        model = req.model
        if "fallback" in self.faults and req.step.startswith("extract"):
            model = FALLBACK_MODEL
        if req.step == "route":
            return self._reply(
                {"doc_type": self.doc_type, "authority": self.authority, "has_arabic": "true"},
                req.model,
            )
        if "refusal" in self.faults and req.step.startswith("extract_primary"):
            return ModelResponse(
                content=[], parsed=None, stop_reason="refusal", serving_model=model, usage=USAGE
            )
        # "malformed" matches the retry step too ("extract_primary_retry"), so both replies fail.
        if "malformed" in self.faults and req.step.startswith("extract_primary"):
            return self._reply({"licence_number": "not a field"}, model)
        # "malformed_once" matches the first step only, so the retry succeeds.
        if "malformed_once" in self.faults and req.step == "extract_primary":
            return self._reply({"licence_number": "not a field"}, model)
        if self.labels is None:
            raise ValueError("extraction requested for a document without labels")
        full = extraction_from_labels(self.labels, self.faults)
        if req.step.startswith("extract_secondary"):
            critical = {name: full[name] for name in CRITICAL_FIELDS}
            if "expired_uncertain" in self.faults:
                # An ink stamp covers the expiry year: the second reading gets the year wrong.
                critical["expiry_date"] = _misread_year(critical["expiry_date"])
            return self._reply(critical, model)
        return self._reply(full, model)

    @staticmethod
    def _reply(parsed: dict[str, Any], model: str) -> ModelResponse:
        return ModelResponse(
            content=[{"type": "text", "text": "{}"}],
            parsed=parsed,
            stop_reason="end_turn",
            serving_model=model,
            usage=USAGE,
        )


class LabelDemoTransport:
    """Demo mode: finds the synthetic case whose licence number appears in the document's
    OCR text and answers from its labels. Documents with no matching case read as
    ``unclear``. Never used in production; ``main.py`` logs a warning when it is on."""

    def __init__(self, cases_dir: Path) -> None:
        self.cases: list[dict[str, Any]] = [
            json.loads(p.read_text("utf-8")) for p in sorted(cases_dir.glob("*.json"))
        ]

    def _case_for(self, req: ModelRequest) -> dict[str, Any] | None:
        text = " ".join(
            part.get("text", "")
            for m in req.messages
            for part in m["content"]
            if isinstance(part, dict)
        )
        for case in self.cases:
            values = case.get("expected_values") or {}
            number = values.get("licence_number")
            if number and number in text:
                return case
        return None

    def send(self, req: ModelRequest) -> ModelResponse:
        case = self._case_for(req)
        if case is None:
            return ScriptedTransport(None, doc_type="unclear", authority="unknown").send(req)
        # Faults that change how a model reads the document, as the case file records them.
        faults = set(case.get("faults", [])) & READING_FAULTS
        if case["expected_values"].get("people") is None:
            faults.add("owners_unclear")
        return ScriptedTransport(case["expected_values"], faults=faults).send(req)
