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
from pydantic_core import ErrorDetails

from licence_kyb.config import StepModel
from licence_kyb.llm.client import (
    LLMClient,
    LLMError,
    ModelRefusedError,
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

MAX_ERRORS_IN_RETRY = 20  # enough for the model to correct; keeps the retry prompt short
EVIDENCE_KEYS = frozenset({"evidence_quote", "page", "self_confidence", "origin"})


@dataclass
class ExtractOutcome:
    primary: TradeLicenceExtraction | None = None
    secondary: CriticalFields | None = None
    agreement: dict[str, bool] = field(default_factory=dict)
    serving_models: list[str] = field(default_factory=list)
    responses: list[tuple[ModelRequest, ModelResponse]] = field(default_factory=list)
    reasons: list[ReasonCode] = field(default_factory=list)
    refused: bool = False
    """The model declined a reading (counted in the daily refusal rate)."""


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
    output: type[BaseModel],
    pages_png: list[bytes],
    ocr_text: str,
    profile: AuthorityProfile,
    cfg: StepModel,
) -> ModelRequest:
    """The request for one reading. The step name is also the name of its prompt file."""
    content = [image_block(png) for png in pages_png]
    content.append({"type": "text", "text": f"OCR text of the document:\n{ocr_text}"})
    return ModelRequest(
        step=step,
        model=cfg.model,
        effort=cfg.effort,
        max_tokens=cfg.max_tokens,
        system=f"{load_prompt(step)}\n\nAuthority profile:\n{_profile_text(profile)}",
        messages=[{"role": "user", "content": content}],
        output_model=output,
    )


@dataclass
class _Reading[M: BaseModel]:
    """What one reading produced. Each thread fills its own reading, so nothing is shared."""

    parsed: M | None = None
    responses: list[tuple[ModelRequest, ModelResponse]] = field(default_factory=list)
    reasons: list[ReasonCode] = field(default_factory=list)
    refused: bool = False


def model_values(raw: Any) -> Any:
    """The model's reply without any ``origin`` key, at any depth. Only a reviewer's action
    sets an origin; a value from the model is always "read" and needs its evidence, so a
    document cannot make the model skip the checks by claiming a reviewer typed a value."""
    if isinstance(raw, dict):
        return {k: model_values(v) for k, v in raw.items() if k != "origin"}
    if isinstance(raw, list):
        return [model_values(v) for v in raw]
    return raw


def _read[M: BaseModel](llm: LLMClient, request: ModelRequest, model: type[M]) -> _Reading[M]:
    reading = _Reading[M]()
    try:
        response = llm.call(request)
    except LLMError as exc:
        reading.reasons.append(exc.reason_code)
        reading.refused = isinstance(exc, ModelRefusedError)
        return reading
    reading.responses.append((request, response))
    if is_fallback(request, response):
        reading.reasons.append("fallback_model")
    try:
        reading.parsed = model.model_validate(model_values(response.parsed))
    except ValidationError as err:
        _retry_once(llm, _retry_request(request, response, err), model, reading)
    return reading


def _retry_once[M: BaseModel](
    llm: LLMClient, retry: ModelRequest, model: type[M], reading: _Reading[M]
) -> None:
    """The one retry after a reply that failed the schema. Any second failure ends the reading."""
    try:
        response = llm.call(retry)
    except LLMError:
        reading.reasons.append("processing_failed")
        return
    reading.responses.append((retry, response))
    try:
        reading.parsed = model.model_validate(model_values(response.parsed))
    except ValidationError:
        reading.reasons.append("processing_failed")


def _error_line(error: ErrorDetails) -> str:
    path = ".".join(str(part) for part in error["loc"]) or "record"
    return f"{path}: {error['msg']}"


def _retry_request(
    request: ModelRequest, response: ModelResponse, err: ValidationError
) -> ModelRequest:
    problems = "; ".join(_error_line(e) for e in err.errors()[:MAX_ERRORS_IN_RETRY])
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
    """A comparable form of a value: text normalised, list order ignored, evidence dropped."""
    if isinstance(value, str):
        return normalise_text(value)
    if isinstance(value, list):
        return sorted(json.dumps(_value_key(v), sort_keys=True, default=str) for v in value)
    if isinstance(value, dict):
        key: dict[str, Any] = {}
        for name, item in value.items():
            if name in EVIDENCE_KEYS:
                continue
            key[name] = _value_key(item.get("value") if isinstance(item, dict) else item)
        return key
    return value


def agreement(primary: TradeLicenceExtraction, secondary: CriticalFields) -> dict[str, bool]:
    """Field-by-field agreement on critical fields; lists compare element by element."""
    result: dict[str, bool] = {}
    first = primary.model_dump(mode="json")
    second = secondary.model_dump(mode="json")
    for name in CRITICAL_FIELDS:
        same_status = first[name]["status"] == second[name]["status"]
        same_value = _value_key(first[name]["value"]) == _value_key(second[name]["value"])
        result[name] = same_status and same_value
    return result


def extract_licence(
    llm: LLMClient, primary_req: ModelRequest, secondary_req: ModelRequest
) -> ExtractOutcome:
    with ThreadPoolExecutor(max_workers=2) as pool:
        primary_job = pool.submit(_read, llm, primary_req, TradeLicenceExtraction)
        secondary_job = pool.submit(_read, llm, secondary_req, CriticalFields)
        primary = primary_job.result()
        secondary = secondary_job.result()
    out = ExtractOutcome(primary=primary.parsed, secondary=secondary.parsed)
    out.responses = [*primary.responses, *secondary.responses]
    out.serving_models = [response.serving_model for _request, response in out.responses]
    if out.primary is not None and out.secondary is not None:
        out.agreement = agreement(out.primary, out.secondary)
    # Both readings can report the same code; keep each code once, in first-seen order.
    out.reasons = list(dict.fromkeys([*primary.reasons, *secondary.reasons]))
    out.refused = primary.refused or secondary.refused
    return out
