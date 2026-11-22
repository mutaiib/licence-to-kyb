"""Intake: accept only safe, supported files, store them encrypted (S2; FR-001 to FR-004).

Runs synchronously in the upload request, before the graph, so the API can answer 422 at
once. The type comes from the file's bytes, never its name. Pixel limits are checked from
headers before any full decode, which stops decompression bombs.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import warnings
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from licence_kyb.nodes.preprocess import POINTS_PER_INCH, RENDER_DPI
from licence_kyb.schemas.results import ReasonCode
from licence_kyb.security import Cipher
from licence_kyb.store.db import Database

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 5
MAX_MEGAPIXELS = 50.0
Image.MAX_IMAGE_PIXELS = int(MAX_MEGAPIXELS * 1_000_000)  # PIL refuses larger images outright

SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


@dataclass(frozen=True)
class IntakeResult:
    run_id: str | None
    reason_code: ReasonCode | None = None
    duplicate: bool = False
    mime: str | None = None
    page_count: int = 0


def sniff(data: bytes) -> str | None:
    return next((mime for magic, mime in SIGNATURES if data.startswith(magic)), None)


def measure(data: bytes, mime: str) -> tuple[int, float]:
    """Page count and the largest page's megapixels at render resolution, without decoding."""
    if mime == "application/pdf":
        doc = pdfium.PdfDocument(data)
        try:
            pages = len(doc)
            worst = 0.0
            for i in range(min(pages, MAX_PAGES + 1)):
                width, height = doc[i].get_size()  # points
                worst = max(worst, width * height * (RENDER_DPI / POINTS_PER_INCH) ** 2 / 1e6)
        finally:
            doc.close()
        return pages, worst
    with warnings.catch_warnings():
        # Oversized images are rejected by the caller; the warning adds nothing.
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as img:  # reads the header only
            return 1, img.width * img.height / 1e6


class IntakeService:
    def __init__(self, db: Database, cipher: Cipher, files_dir: Path) -> None:
        self.db = db
        self.cipher = cipher
        self.files_dir = files_dir

    def stored_path(self, run_id: str) -> Path:
        return self.files_dir / run_id / "original.bin"

    def read_original(self, run_id: str) -> bytes:
        return self.cipher.decrypt(self.stored_path(run_id).read_bytes())

    def accept(self, data: bytes, *, applicant_name: str) -> IntakeResult:
        reason, mime, pages, megapixels = self._check(data)
        sha = hashlib.sha256(data).hexdigest()
        run = self.db.create_run(
            run_id=str(uuid.uuid4()),
            file_sha256=sha,
            applicant_name=self.cipher.encrypt_text(applicant_name),
        )
        if run.status != "received" or self.stored_path(run.run_id).exists():
            return IntakeResult(run.run_id, duplicate=True, mime=mime, page_count=pages)
        if reason is not None:
            reasons = [{"code": reason, "field": None, "rule_id": None}]
            self.db.update_run(
                run.run_id, status="rejected", route="reject", reasons_json=json.dumps(reasons)
            )
            return IntakeResult(run.run_id, reason_code=reason, mime=mime)
        assert mime is not None  # noqa: S101 - a file of unknown type is refused above
        path = self.stored_path(run.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.cipher.encrypt(data))
        self.db.record_file(
            run_id=run.run_id,
            mime=mime,
            page_count=pages,
            megapixels=megapixels,
            encrypted_path=str(path),
        )
        return IntakeResult(run.run_id, mime=mime, page_count=pages)

    def _check(self, data: bytes) -> tuple[ReasonCode | None, str | None, int, float]:
        mime = sniff(data)
        reason = _size_and_type_reason(data, mime)
        if reason is not None or mime is None:
            return reason, mime, 0, 0.0
        try:
            pages, megapixels = measure(data, mime)
        except Image.DecompressionBombError:
            return "image_too_large", mime, 0, 0.0
        except Exception:  # any parse failure means the file is unreadable
            return "unreadable_file", mime, 0, 0.0
        return _page_reason(pages, megapixels), mime, pages, megapixels


def _size_and_type_reason(data: bytes, mime: str | None) -> ReasonCode | None:
    if len(data) > MAX_BYTES:
        return "too_large"
    if mime is None:
        return "invalid_type"
    return None


def _page_reason(pages: int, megapixels: float) -> ReasonCode | None:
    if pages == 0:
        return "unreadable_file"
    if pages > MAX_PAGES:
        return "too_many_pages"
    if megapixels > MAX_MEGAPIXELS:
        return "image_too_large"
    return None
