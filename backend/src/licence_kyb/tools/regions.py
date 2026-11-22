"""Page regions the tools can read, as fractions of the page (x0, y0, x1, y1)."""

from __future__ import annotations

from licence_kyb.nodes.preprocess import Word

REGIONS: dict[str, tuple[float, float, float, float]] = {
    "top_left": (0.0, 0.0, 0.5, 0.5),
    "top_right": (0.5, 0.0, 1.0, 0.5),
    "middle": (0.0, 0.33, 1.0, 0.67),
    "bottom_left": (0.0, 0.5, 0.5, 1.0),
    "bottom_right": (0.5, 0.5, 1.0, 1.0),
    "full_page": (0.0, 0.0, 1.0, 1.0),
}


def words_in(words: list[Word], page: int, region: str) -> list[Word]:
    """The words on ``page`` whose centre is inside ``region``."""
    x0, y0, x1, y1 = REGIONS[region]
    return [
        w
        for w in words
        if w.page == page
        and x0 <= (w.bbox[0] + w.bbox[2]) / 2 <= x1
        and y0 <= (w.bbox[1] + w.bbox[3]) / 2 <= y1
    ]
