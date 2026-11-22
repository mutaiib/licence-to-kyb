"""The review page's evidence box covers the whole quote, in visual order (US1 visual check)."""

from __future__ import annotations

from licence_kyb.api.views import _evidence_box


def word(text: str, x0: float, x1: float, y: float = 0.5) -> dict[str, object]:
    return {"page": 1, "text": text, "bbox": [x0, y - 0.005, x1, y + 0.005], "conf": 1.0}


def test_the_box_spans_label_and_value_even_when_extraction_order_differs() -> None:
    # PDF extraction order: label, Arabic label (far right), then the value in the middle.
    words = [
        word("Expiry", 0.08, 0.13),
        word("Date", 0.14, 0.18),
        word("تاريخ", 0.85, 0.9),
        word("11/06/2026", 0.33, 0.45),
    ]

    box = _evidence_box(words, "Expiry Date 11/06/2026", page=1)

    assert box is not None
    assert box.x <= 0.08
    assert box.x + box.w >= 0.45
    assert box.x + box.w < 0.85  # the Arabic label is not part of the quote
