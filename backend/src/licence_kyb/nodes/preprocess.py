"""Read the document: page images, words with boxes, and the QR payload (S2; FR-007).

- PDF pages are rendered at 200 DPI; a text layer is used when present, else Tesseract.
- Photos are auto-rotated (EXIF, then Tesseract orientation detection) before OCR.
- The QR payload is untrusted text: it is decoded and stored, never opened or fetched.
Word boxes are normalised to 0..1 of the page, for the review page's evidence highlight.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import cv2
import numpy as np
import pdfplumber
import pypdfium2 as pdfium
import pytesseract
from PIL import Image, ImageOps

RENDER_DPI = 200
POINTS_PER_INCH = 72  # PDF page sizes are in points
OCR_LANG = "eng+ara"
MIN_TEXT_LAYER_WORDS = 5
OCR_TIMEOUT_SECONDS = 30
ROW_TOLERANCE = 0.006  # fraction of page height


@dataclass(frozen=True)
class Word:
    page: int
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 as fractions of the page
    conf: float  # 0..1


@dataclass
class PageSet:
    page_count: int
    words: list[Word] = field(default_factory=list)
    qr_payload: str | None = None
    images: list[bytes] = field(default_factory=list)  # PNG per page
    source: str = "ocr"  # "text_layer" or "ocr"

    @property
    def text(self) -> str:
        """Words grouped into visual rows, each row read left to right."""
        return "\n".join(" ".join(w.text for w in row) for row in visual_rows(self.words))


def visual_rows(words: list[Word]) -> list[list[Word]]:
    """Group words into rows by vertical centre, then order each row left to right.
    PDF text layers return words in extraction order, which splits labels from values."""
    rows: list[list[Word]] = []
    for w in sorted(words, key=lambda w: (w.page, (w.bbox[1] + w.bbox[3]) / 2)):
        centre = (w.bbox[1] + w.bbox[3]) / 2
        last = rows[-1] if rows else None
        if last and last[0].page == w.page and abs(_centre(last) - centre) <= ROW_TOLERANCE:
            last.append(w)
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w.bbox[0]) for r in rows]


def _centre(row: list[Word]) -> float:
    return sum((w.bbox[1] + w.bbox[3]) / 2 for w in row) / len(row)


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _render_pdf(data: bytes) -> list[Image.Image]:
    doc = pdfium.PdfDocument(data)
    try:
        return [
            doc[i].render(scale=RENDER_DPI / POINTS_PER_INCH).to_pil().convert("RGB")
            for i in range(len(doc))
        ]
    finally:
        doc.close()


def _text_layer(data: bytes) -> list[Word]:
    words: list[Word] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            w, h = float(page.width), float(page.height)
            for item in page.extract_words(keep_blank_chars=False, use_text_flow=True):
                words.append(
                    Word(
                        number,
                        str(item["text"]),
                        (item["x0"] / w, item["top"] / h, item["x1"] / w, item["bottom"] / h),
                        1.0,
                    )
                )
    return words


def _upright(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img) or img
    try:
        osd = pytesseract.image_to_osd(
            img, output_type=pytesseract.Output.DICT, timeout=OCR_TIMEOUT_SECONDS
        )
        angle = int(osd.get("rotate", 0))
    except (pytesseract.TesseractError, RuntimeError):
        angle = 0  # too little text to tell; keep as is
    return img.rotate(-angle, expand=True, fillcolor="white") if angle else img


def _ocr(img: Image.Image, page: int) -> list[Word]:
    data = pytesseract.image_to_data(
        img, lang=OCR_LANG, output_type=pytesseract.Output.DICT, timeout=OCR_TIMEOUT_SECONDS
    )
    w, h = img.size
    words: list[Word] = []
    for i, text in enumerate(data["text"]):
        conf = float(data["conf"][i])
        if not text.strip() or conf < 0:
            continue
        left, top, width, height = (data[k][i] for k in ("left", "top", "width", "height"))
        words.append(
            Word(
                page, text, (left / w, top / h, (left + width) / w, (top + height) / h), conf / 100
            )
        )
    return words


def _qr(images: list[Image.Image]) -> str | None:
    detector = cv2.QRCodeDetector()
    for img in images:
        payload, _points, _ = detector.detectAndDecode(np.array(img.convert("RGB")))
        if payload:
            return str(payload)
    return None


def preprocess_file(data: bytes, mime: str) -> PageSet:
    if mime == "application/pdf":
        images = _render_pdf(data)
        words = _text_layer(data)
        source = "text_layer"
        if len(words) < MIN_TEXT_LAYER_WORDS:  # a scanned PDF: OCR the rendered pages
            words = [w for n, img in enumerate(images, start=1) for w in _ocr(img, n)]
            source = "ocr"
    else:
        with Image.open(io.BytesIO(data)) as raw:
            images = [_upright(raw.convert("RGB"))]
        words = _ocr(images[0], 1)
        source = "ocr"
    return PageSet(
        page_count=len(images),
        words=words,
        qr_payload=_qr(images),
        images=[_png(img) for img in images],
        source=source,
    )
