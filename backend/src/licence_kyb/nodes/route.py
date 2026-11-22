"""Route: what document is this, and who issued it? One model call, no tools (S3).

Code checks after the call (data-model.md, RouteResult):
- a labelled licence number in the OCR text that matches a different authority makes the
  authority ``unknown``;
- an out-of-scope label is accepted only when the text has no labelled licence number and
  no licence title (FR-006); otherwise the document goes to review as ``unclear_document``.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass

from licence_kyb.llm.client import LLMClient, LLMError, ModelRequest, ModelResponse
from licence_kyb.llm.prompts import load_prompt
from licence_kyb.profiles import AUTHORITIES, load_profile
from licence_kyb.schemas.licence import RouteResult
from licence_kyb.schemas.results import ReasonCode

OUT_OF_SCOPE = frozenset({"moa", "emirates_id", "passport", "other"})
LABEL_WINDOW = 40
ROUTE_OCR_CHARS = 1500


@dataclass(frozen=True)
class RouteOutcome:
    doc_type: str
    authority: str
    reasons: tuple[ReasonCode, ...] = ()
    response: ModelResponse | None = None

    @property
    def is_licence(self) -> bool:
        return self.doc_type == "trade_licence"


def _all_labels() -> list[str]:
    labels = {
        label
        for code in (*AUTHORITIES, "generic")
        for label in load_profile(code).licence_number_labels
    }
    return sorted(labels, key=len, reverse=True)


def labelled_numbers(text: str) -> list[tuple[str, str]]:
    """(authority, number) for authority-pattern tokens within 40 characters after a label
    on the same line. Digits inside other identifiers (e.g. 784-1990-1234567-1) don't count."""
    found: list[tuple[str, str]] = []
    labels = _all_labels()
    for line in text.splitlines():
        lowered = line.casefold()
        for label in labels:
            start = lowered.find(label.casefold())
            if start < 0:
                continue
            window = line[start + len(label) : start + len(label) + LABEL_WINDOW]
            for token in re.findall(r"[A-Za-z0-9-]+", window):
                for code in AUTHORITIES:
                    if load_profile(code).matches_number(token):
                        found.append((code, token))
            break
    return found


def has_licence_title(text: str) -> bool:
    lowered = text.casefold()
    return any(
        title.casefold() in lowered
        for code in (*AUTHORITIES, "generic")
        for title in load_profile(code).licence_titles
    )


def build_route_request(
    page_png: bytes, ocr_text: str, model: str, effort: str, max_tokens: int
) -> ModelRequest:
    return ModelRequest(
        step="route",
        model=model,
        effort=effort,
        max_tokens=max_tokens,
        system=load_prompt("route"),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(page_png).decode(),
                        },
                    },
                    {
                        "type": "text",
                        "text": f"OCR text of page 1 (first {ROUTE_OCR_CHARS} characters):\n"
                        f"{ocr_text[:ROUTE_OCR_CHARS]}",
                    },
                ],
            }
        ],
        output_model=RouteResult,
    )


def route_document(llm: LLMClient, request: ModelRequest, ocr_text: str) -> RouteOutcome:
    try:
        response = llm.call(request)
        result = response.parsed_as(RouteResult)
    except (LLMError, ValueError) as exc:
        code: ReasonCode = getattr(exc, "reason_code", "processing_failed")
        return RouteOutcome("unclear", "unknown", (code,))
    return decide_route(result, ocr_text, response)


def decide_route(
    result: RouteResult, ocr_text: str, response: ModelResponse | None = None
) -> RouteOutcome:
    numbers = labelled_numbers(ocr_text)
    if result.doc_type in OUT_OF_SCOPE:
        if numbers or has_licence_title(ocr_text):
            return RouteOutcome("unclear", "unknown", ("unclear_document",), response)
        return RouteOutcome(result.doc_type, "unknown", ("out_of_scope",), response)
    if result.doc_type == "unclear":
        return RouteOutcome("unclear", "unknown", ("unclear_document",), response)
    authority = result.authority
    number_authorities = {code for code, _ in numbers}
    if number_authorities and authority not in number_authorities:
        return RouteOutcome("trade_licence", "unknown", ("unknown_authority",), response)
    if authority not in AUTHORITIES:
        return RouteOutcome("trade_licence", "unknown", ("unknown_authority",), response)
    return RouteOutcome("trade_licence", authority, (), response)
