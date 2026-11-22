"""ScriptedTransport: model responses written from a case's labels (research R10a).

It answers like a model that reads the document correctly, unless a fault asks otherwise.
Faults: ``malformed`` (invalid twice), ``malformed_once`` (invalid, then valid),
``refusal``, ``fallback``, ``route_as:<doc_type>:<authority>``, ``people_unclear``.
"""

from __future__ import annotations

from typing import Any

from licence_kyb.llm.client import ModelRequest, ModelResponse, Usage
from licence_kyb.testdata.render import AUTHORITY_TITLE, LABELS
from licence_kyb.testdata.spec import LEGAL_FORMS

USAGE = Usage(input_tokens=9000, output_tokens=2500, thinking_tokens=1200, cache_read_tokens=3000)
FORM_LABEL = {code: en for forms in LEGAL_FORMS.values() for code, en, _ar in forms}


def present(value: Any, quote: str) -> dict[str, Any]:
    return {
        "value": value,
        "status": "present",
        "origin": "read",
        "evidence_quote": quote,
        "page": 1,
        "self_confidence": "high",
    }


def absent(status: str = "not_present") -> dict[str, Any]:
    return {
        "value": None,
        "status": status,
        "origin": "read",
        "evidence_quote": None,
        "page": None,
        "self_confidence": "unknown",
    }


def dmy(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"


def extraction_from_labels(v: dict[str, Any], faults: set[str]) -> dict[str, Any]:
    def labelled(key: str, value: str, printed: str | None = None) -> dict[str, Any]:
        return present(value, f"{LABELS[key][0]} {printed or value}")

    people: dict[str, Any]
    if v["people"] is None or "people_unclear" in faults:
        people = absent("unclear")
    else:
        people = present(
            [
                {
                    "name": present(p["name"], p["name"]),
                    "nationality": present(p["nationality"], p["nationality"]),
                    "role": present(p["role"], p["role"].title()),
                    "share_pct": present(p["share_pct"], f"{p['share_pct']:g}%")
                    if p["share_pct"] is not None
                    else absent(),
                }
                for p in v["people"]
            ],
            " ".join(p["name"] for p in v["people"]),
        )
    return {
        "licence_number": labelled("licence_number", v["licence_number"]),
        "unified_licence_number": absent(),
        "register_number": absent(),
        "chamber_number": labelled("chamber_number", v["chamber_number"]),
        "trade_name_en": labelled("trade_name_en", v["trade_name_en"]),
        "trade_name_ar": present(v["trade_name_ar"], v["trade_name_ar"])
        if v.get("trade_name_ar")
        else absent(),
        "legal_form": present(v["legal_form"], FORM_LABEL.get(v["legal_form"], v["legal_form"])),
        "licence_category": absent(),
        "licence_type": absent(),
        "issuing_authority": present(
            v["issuing_authority"], AUTHORITY_TITLE[v["issuing_authority"]][0]
        ),
        "establishment_date": labelled(
            "establishment_date", v["establishment_date"], dmy(v["establishment_date"])
        ),
        "issue_date": labelled("issue_date", v["issue_date"], dmy(v["issue_date"])),
        "expiry_date": labelled("expiry_date", v["expiry_date"], dmy(v["expiry_date"])),
        "activities": present(
            [
                {
                    "code": present(a["code"], a["code"]),
                    "description_en": present(a["description_en"], a["description_en"]),
                    "description_ar": absent(),
                }
                for a in v["activities"]
            ],
            " ".join(f"{a['code']} {a['description_en']}" for a in v["activities"]),
        ),
        "people": people,
        "address": labelled("address", v["address"]),
    }


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
        model = (
            "claude-sonnet-5-5"
            if "fallback" in self.faults and req.step.startswith("extract")
            else req.model
        )
        if req.step == "route":
            return self._reply(
                {"doc_type": self.doc_type, "authority": self.authority, "has_arabic": "true"},
                req.model,
            )
        if "refusal" in self.faults and req.step.startswith("extract_primary"):
            return ModelResponse(
                content=[], parsed=None, stop_reason="refusal", serving_model=model, usage=USAGE
            )
        if "malformed" in self.faults and req.step.startswith("extract_primary"):
            return self._reply({"licence_number": "not a field"}, model)
        if "malformed_once" in self.faults and req.step == "extract_primary":
            return self._reply({"licence_number": "not a field"}, model)
        assert self.labels is not None
        full = extraction_from_labels(self.labels, self.faults)
        if req.step.startswith("extract_secondary"):
            keys = (
                "licence_number",
                "trade_name_en",
                "trade_name_ar",
                "legal_form",
                "expiry_date",
                "people",
            )
            return self._reply({k: full[k] for k in keys}, model)
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
