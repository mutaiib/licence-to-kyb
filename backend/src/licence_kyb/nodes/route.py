"""Route: what document is this, and who issued it? One model call, no tools (S3).

Code checks after the call (data-model.md, RouteResult):
- a labelled licence number in the OCR text that matches a different authority makes the
  authority ``unknown``;
- an out-of-scope label is accepted only when the text has no labelled licence number and
  no licence title (FR-006); otherwise the document goes to review as ``unclear_document``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from licence_kyb.config import StepModel
from licence_kyb.llm.client import (
    LLMClient,
    LLMError,
    ModelRefusedError,
    ModelRequest,
    ModelResponse,
    image_block,
)
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
    refused: bool = False
    """The model declined to classify the document (counted in the daily refusal rate)."""


def _all_labels() -> list[str]:
    labels = {
        label
        for code in (*AUTHORITIES, "generic")
        for label in load_profile(code).licence_number_labels
    }
    return sorted(labels, key=len, reverse=True)


def _text_after_label(line: str, labels: list[str]) -> str | None:
    """The ``LABEL_WINDOW`` characters after the first label in ``line``, or None.

    Only one label counts per line. The labels are sorted longest first, so a long label
    such as "Licence No." is found before a shorter label that it contains.
    """
    lowered = line.casefold()
    for label in labels:
        start = lowered.find(label.casefold())
        if start >= 0:
            end = start + len(label)
            return line[end : end + LABEL_WINDOW]
    return None


def _numbers_in(window: str) -> list[tuple[str, str]]:
    """(authority, token) for each whole token that matches an authority's number pattern."""
    found: list[tuple[str, str]] = []
    for token in re.findall(r"[A-Za-z0-9-]+", window):
        for code in AUTHORITIES:
            if load_profile(code).matches_number(token):
                found.append((code, token))
    return found


def labelled_numbers(text: str) -> list[tuple[str, str]]:
    """(authority, number) for each licence number printed just after a label, on the same line.

    Tokens are whole, so digits inside other identifiers (e.g. 784-1990-1234567-1) don't count.
    """
    labels = _all_labels()
    found: list[tuple[str, str]] = []
    for line in text.splitlines():
        window = _text_after_label(line, labels)
        if window is not None:
            found.extend(_numbers_in(window))
    return found


def has_licence_title(text: str) -> bool:
    lowered = text.casefold()
    return any(
        title.casefold() in lowered
        for code in (*AUTHORITIES, "generic")
        for title in load_profile(code).licence_titles
    )


def build_route_request(page_png: bytes, ocr_text: str, cfg: StepModel) -> ModelRequest:
    return ModelRequest(
        step="route",
        model=cfg.model,
        effort=cfg.effort,
        max_tokens=cfg.max_tokens,
        system=load_prompt("route"),
        messages=[
            {
                "role": "user",
                "content": [
                    image_block(page_png),
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
    except LLMError as exc:
        refused = isinstance(exc, ModelRefusedError)
        return RouteOutcome("unclear", "unknown", (exc.reason_code,), refused=refused)
    try:
        result = response.parsed_as(RouteResult)
    except ValueError:  # no parsed output, or output that does not match the schema
        return RouteOutcome("unclear", "unknown", ("processing_failed",))
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
    number_authorities = {code for code, _number in numbers}
    contradicts_number = bool(number_authorities) and result.authority not in number_authorities
    if contradicts_number or result.authority not in AUTHORITIES:
        return RouteOutcome("trade_licence", "unknown", ("unknown_authority",), response)
    return RouteOutcome("trade_licence", result.authority, (), response)
