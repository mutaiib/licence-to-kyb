"""Intake and reading, from the "Intake and reading" table in test-cases.md (S2)."""

from __future__ import annotations

import io
import socket
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from PIL import Image

from licence_kyb.nodes.intake import IntakeService
from licence_kyb.nodes.preprocess import preprocess_file
from licence_kyb.security import Cipher
from licence_kyb.store.db import Database
from licence_kyb.testdata.degrade import degrade, rasterise
from licence_kyb.testdata.render import render_licence, render_other
from licence_kyb.testdata.spec import make_spec


@pytest.fixture
def service(tmp_path: Path) -> IntakeService:
    db = Database(tmp_path / "app.sqlite3")
    db.migrate()
    return IntakeService(db, Cipher([Fernet.generate_key().decode()]), tmp_path / "files")


def licence_pdf(seed: int = 1, authority: str = "DET") -> bytes:
    return render_licence(make_spec("t", authority, "A", set(), seed))


def multi_page_pdf(pages: int) -> bytes:
    from reportlab.pdfgen.canvas import Canvas  # noqa: PLC0415 - test-only helper

    buf = io.BytesIO()
    c = Canvas(buf)
    for i in range(pages):
        c.drawString(100, 700, f"page {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def png(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("L", (width, height), 255).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- intake limits
def test_one_page_pdf_is_accepted(service: IntakeService) -> None:
    result = service.accept(licence_pdf(), applicant_name="Acme")
    assert result.reason_code is None
    assert result.run_id


@pytest.mark.parametrize(
    ("make", "reason"),
    [
        (lambda: multi_page_pdf(6), "too_many_pages"),
        (lambda: b"\xff\xd8\xff\xe0" + b"\0" * (11 * 1024 * 1024), "too_large"),
        (lambda: png(9000, 9000), "image_too_large"),
        (lambda: b"MZ\x90\x00" + b"\0" * 1000, "invalid_type"),
        (lambda: b"%PDF-1.7\n%broken" + b"\0" * 200, "unreadable_file"),
    ],
)
def test_files_outside_the_limits_are_rejected_with_a_reason_code(
    service: IntakeService, make: object, reason: str
) -> None:
    result = service.accept(make(), applicant_name="Acme")  # type: ignore[operator]
    assert result.reason_code == reason


def test_the_same_file_uploaded_twice_gives_one_run(service: IntakeService) -> None:
    pdf = licence_pdf()
    first = service.accept(pdf, applicant_name="Acme")
    second = service.accept(pdf, applicant_name="Acme")

    assert second.run_id == first.run_id
    assert second.duplicate
    assert service.db.count("runs") == 1


def test_the_stored_file_is_encrypted_and_decrypts_to_the_original(service: IntakeService) -> None:
    pdf = licence_pdf()
    result = service.accept(pdf, applicant_name="Acme")

    stored = service.stored_path(result.run_id).read_bytes()
    assert pdf not in stored
    assert service.read_original(result.run_id) == pdf


# ---------------------------------------------------------------- reading
def test_a_text_layer_pdf_yields_words_with_boxes_and_the_qr_payload() -> None:
    spec = make_spec("t", "DET", "A", set(), 3)
    pages = preprocess_file(render_licence(spec), "application/pdf")

    assert pages.page_count == 1
    assert spec.printed_licence_number in pages.text
    assert all(0 <= w.bbox[0] <= 1 and 0 <= w.bbox[3] <= 1 for w in pages.words)
    assert pages.qr_payload == spec.qr_payload


def test_a_qr_code_holding_a_url_is_kept_as_text_and_never_fetched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*_a: object, **_k: object) -> None:
        raise AssertionError("no network access while reading a document")

    monkeypatch.setattr(socket, "create_connection", refuse)
    spec = make_spec("t", "DET", "A", set(), 4)
    spec = type(spec)(**{**spec.__dict__, "qr_payload": "https://example.invalid/verify?id=1"})

    pages = preprocess_file(render_licence(spec), "application/pdf")

    assert pages.qr_payload == "https://example.invalid/verify?id=1"


def test_a_photo_rotated_90_degrees_is_read_upright() -> None:
    spec = make_spec("t", "DET", "A", set(), 5)
    image, mime = degrade(render_licence(spec), ["rotate_90"], seed=5)

    pages = preprocess_file(image, mime)

    assert "Trade Name" in pages.text or spec.trade_name_en.split()[0] in pages.text


def test_an_image_only_scan_yields_arabic_words() -> None:
    spec = make_spec("t", "ADDED", "A", set(), 6)
    image, mime = degrade(render_licence(spec), ["jpeg"], seed=6)

    pages = preprocess_file(image, mime)

    assert any("؀" <= ch <= "ۿ" for ch in pages.text)


def test_a_blank_page_reads_without_crashing() -> None:
    pages = preprocess_file(render_other("blank"), "application/pdf")
    assert pages.page_count == 1
    assert pages.qr_payload is None


def test_page_images_are_returned_for_the_document_viewer() -> None:
    pages = preprocess_file(licence_pdf(), "application/pdf")
    (image,) = pages.images
    assert isinstance(rasterise(licence_pdf()), Image.Image)
    assert image.startswith(b"\x89PNG")
