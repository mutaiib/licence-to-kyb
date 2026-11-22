"""Turn a rendered PDF into a scan or a phone photo (research R9a).

Each degradation is deterministic for a given seed, so the same catalogue always produces
the same images.
"""

from __future__ import annotations

import io
import random
from typing import Literal

import cv2
import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFilter

Degradation = Literal[
    "blur", "jpeg", "low_dpi", "rotate_small", "rotate_90", "perspective", "stamp"
]


def rasterise(pdf: bytes, dpi: int = 200) -> Image.Image:
    doc = pdfium.PdfDocument(pdf)
    try:
        page = doc[0]
        image: Image.Image = page.render(scale=dpi / 72).to_pil().convert("RGB")
    finally:
        doc.close()
    return image


def degrade(pdf: bytes, steps: list[Degradation], seed: int) -> tuple[bytes, str]:
    """Return (image bytes, mime type)."""
    rng = random.Random(seed)
    dpi = 100 if "low_dpi" in steps else 200
    img = rasterise(pdf, dpi=dpi)
    for step in steps:
        if step == "blur":
            img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(1.0, 1.8)))
        elif step == "rotate_small":
            img = img.rotate(rng.uniform(-3, 3), expand=True, fillcolor="white")
        elif step == "rotate_90":
            img = img.rotate(90, expand=True, fillcolor="white")
        elif step == "perspective":
            img = _perspective(img, rng)
        elif step == "stamp":
            img = _stamp(img, rng)
    quality = rng.randint(30, 60) if "jpeg" in steps else 90
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue(), "image/jpeg"


def _perspective(img: Image.Image, rng: random.Random) -> Image.Image:
    arr = np.array(img)
    h, w = arr.shape[:2]
    jitter = [rng.uniform(0.01, 0.05) for _ in range(8)]
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    dst = np.array(
        [
            [w * jitter[0], h * jitter[1]],
            [w * (1 - jitter[2]), h * jitter[3]],
            [w * (1 - jitter[4]), h * (1 - jitter[5])],
            [w * jitter[6], h * (1 - jitter[7])],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(arr, matrix, (w, h), borderValue=(235, 235, 230))
    return Image.fromarray(warped)


def _stamp(img: Image.Image, rng: random.Random) -> Image.Image:
    overlay = img.copy()
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    cx, cy, r = int(w * rng.uniform(0.5, 0.8)), int(h * rng.uniform(0.3, 0.5)), int(w * 0.07)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(40, 60, 160), width=max(w // 200, 3))
    return Image.blend(img, overlay, 0.7)
