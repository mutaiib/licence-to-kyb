"""Extract: two independent readings, no tools (S3; contracts/model-calls.md).

- The primary pass fills ``TradeLicenceExtraction``; the secondary pass reads only the
  critical fields, with different wording and no access to the primary output.
- Both run in parallel. A reply that fails schema validation gets one retry that names the
  failing fields; a second failure, a refusal or a truncated reply ends with
  ``processing_failed``.
- A fallback serving model adds ``fallback_model``: thresholds were calibrated on the primary.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from typing import Any

from pydantic import BaseModel, ValidationError

from licence_kyb.llm.client import (
    LLMClient,
    LLMError,
    ModelRequest,
    ModelResponse,
    image_block,
    is_fallback,
)
from licence_kyb.llm.prompts import load_prompt
from licence_kyb.profiles import AuthorityProfile
from licence_kyb.rules.base import normalise_text
from licence_kyb.schemas.licence import CRITICAL_FIELDS, CriticalFields, TradeLicenceExtraction
from licence_kyb.schemas.results import ReasonCode


@dataclass
class ExtractOutcome:
    primary: TradeLicenceExtraction | None = None
    secondary: CriticalFields | None = None
    agreement: dict[str, bool] = field(default_factory=dict)
    serving_models: list[str] = field(default_factory=list)
    responses: list[tuple[ModelRequest, ModelResponse]] = field(default_factory=list)
    reasons: list[ReasonCode] = field(default_factory=list)


def _profile_text(profile: AuthorityProfile) -> str:
    return json.dumps(
        {
            "authority": profile.code,
            "licence_number_labels": profile.licence_number_labels,
            "licence_number_format": profile.number_pattern,
            "date_format": profile.date_format,
            "allowed_legal_forms": profile.allowed_legal_forms,
        },
        ensure_ascii=False,
    )


def build_extract_request(
    *,
    step: str,
    prompt: str,
    output: type[BaseModel],
    pages_png: list[bytes],
    ocr_text: str,
    profile: AuthorityProfile,
    model: str,
    effort: str,
    max_tokens: int,
) -> ModelRequest:
    content = [image_block(png) for png in pages_png]
    content.append({"type": "text", "text": f"OCR text of the document:\n{ocr_text}"})
    return ModelRequest(
        step=step,
        model=model,
        effort=effort,
        max_tokens=max_tokens,
        system=f"{load_prompt(prompt)}\n\nAuthority profile:\n{_profile_text(profile)}",
        messages=[{"role": "user", "content": content}],
        output_model=output,
    )


def _call_validated[M: BaseModel](
    llm: LLMClient, request: ModelRequest, model: type[M], out: ExtractOutcome
) -> M | None:
    try:
        response = llm.call(request)
    except LLMError as exc:
        out.reasons.append(exc.reason_code)
        return None
    out.responses.append((request, response))
    out.serving_models.append(response.serving_model)
    if is_fallback(request, response):
        out.reasons.append("fallback_model")
    try:
        return model.model_validate(response.parsed)
    except ValidationError as err:
        retry = _retry_request(request, response, err)
    try:
        second = llm.call(retry)
        out.responses.append((retry, second))
        out.serving_models.append(second.serving_model)
        return model.model_validate(second.parsed)
    except (LLMError, ValidationError):
        out.reasons.append("processing_failed")
        return None


def _retry_request(
    request: ModelRequest, response: ModelResponse, err: ValidationError
) -> ModelRequest:
    problems = "; ".join(
        f"{'.'.join(str(p) for p in e['loc']) or 'record'}: {e['msg']}" for e in err.errors()[:20]
    )
    feedback = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Your answer did not match the schema. Correct only these fields "
                f"and answer again with the full structured output: {problems}",
            }
        ],
    }
    previous = {
        "role": "assistant",
        "content": response.content or [{"type": "text", "text": "{}"}],
    }
    return replace(
        request, step=f"{request.step}_retry", messages=[*request.messages, previous, feedback]
    )


def _value_key(value: Any) -> Any:
    if isinstance(value, str):
        return normalise_text(value)
    if isinstance(value, list):
        return sorted(json.dumps(_value_key(v), sort_keys=True, default=str) for v in value)
    if isinstance(value, dict):
        return {
            k: _value_key(v.get("value") if isinstance(v, dict) else v)
            for k, v in value.items()
            if k not in {"evidence_quote", "page", "self_confidence", "origin"}
        }
    return value


def agreement(primary: TradeLicenceExtraction, secondary: CriticalFields) -> dict[str, bool]:
    """Field-by-field agreement on critical fields; lists compare element by element."""
    result: dict[str, bool] = {}
    p_dump, s_dump = primary.model_dump(mode="json"), secondary.model_dump(mode="json")
    for name in CRITICAL_FIELDS:
        a, b = p_dump[name], s_dump[name]
        result[name] = a["status"] == b["status"] and _value_key(a["value"]) == _value_key(
            b["value"]
        )
    return result


def extract_licence(
    llm: LLMClient, primary_req: ModelRequest, secondary_req: ModelRequest
) -> ExtractOutcome:
    out = ExtractOutcome()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_call_validated, llm, primary_req, TradeLicenceExtraction, out)
        second = pool.submit(_call_validated, llm, secondary_req, CriticalFields, out)
        out.primary, out.secondary = first.result(), second.result()
    if out.primary is not None and out.secondary is not None:
        out.agreement = agreement(out.primary, out.secondary)
    out.reasons = list(dict.fromkeys(out.reasons))
    return out
