"""Render synthetic documents to PDF with a real text layer (research R9a).

Every page carries the watermark "SPECIMEN — SYNTHETIC" and a generic logo. No real
authority branding is reproduced. Arabic is shaped with arabic-reshaper and python-bidi.
"""

from __future__ import annotations

import io
import os
from datetime import date
from pathlib import Path

import arabic_reshaper
import qrcode
import qrcode.image.pil
from bidi.algorithm import get_display
from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from licence_kyb.testdata.spec import LicenceSpec

FONT_DIR = Path(os.environ.get("LKYB_FONT_DIR", "/usr/share/fonts/truetype/noto"))
WIDTH, HEIGHT = A4
GREY = Color(0.45, 0.45, 0.45)
LIGHT = Color(0.93, 0.93, 0.93)

AUTHORITY_TITLE = {
    "DET": ("Commercial License", "رخصة تجارية", "Department of Economy - Dubai (synthetic)"),
    "ADDED": (
        "Abu Dhabi Economic Licence",
        "رخصة أبوظبي الاقتصادية",
        "Economic Development - Abu Dhabi (synthetic)",
    ),
    "DMCC": ("Trade Licence", "رخصة تجارية", "Commodities Free Zone (synthetic)"),
    "IFZA": ("Commercial Licence", "رخصة تجارية", "International Free Zone (synthetic)"),
}
LABELS = {
    "licence_number": ("Licence No", "رقم الرخصة"),
    "trade_name_en": ("Trade Name", "الاسم التجاري"),
    "trade_name_ar": ("Trade Name (Arabic)", "الاسم التجاري بالعربية"),
    "legal_form": ("Legal Form", "الشكل القانوني"),
    "issue_date": ("Issue Date", "تاريخ الإصدار"),
    "expiry_date": ("Expiry Date", "تاريخ الانتهاء"),
    "establishment_date": ("Establishment Date", "تاريخ التأسيس"),
    "chamber_number": ("Chamber No", "رقم الغرفة"),
    "address": ("Address", "العنوان"),
}
ROLE_AR = {"owner": "مالك", "manager": "مدير"}

_registered = False


def _fonts() -> None:
    global _registered  # noqa: PLW0603 - one-time font registration
    if _registered:
        return
    pdfmetrics.registerFont(TTFont("Sans", str(FONT_DIR / "NotoSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Sans-Bold", str(FONT_DIR / "NotoSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Arabic", str(FONT_DIR / "NotoNaskhArabic-Regular.ttf")))
    _registered = True


def ar(text: str) -> str:
    """Shape Arabic for a left-to-right PDF text layer."""
    return str(get_display(arabic_reshaper.reshape(text)))


def _dmy(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _canvas(buf: io.BytesIO) -> Canvas:
    _fonts()
    c = Canvas(buf, pagesize=A4, invariant=1)  # invariant: identical bytes for the same input
    c.setTitle("Synthetic document - SPECIMEN")
    return c


def _watermark(c: Canvas) -> None:
    c.saveState()
    c.setFillColor(Color(0.85, 0.85, 0.85, alpha=0.5))
    c.setFont("Sans-Bold", 42)
    c.translate(WIDTH / 2, HEIGHT / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, "SPECIMEN — SYNTHETIC")
    c.restoreState()


def _logo(c: Canvas, x: float, y: float) -> None:
    c.setFillColor(GREY)
    c.circle(x, y, 9 * mm, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Sans-Bold", 9)
    c.drawCentredString(x, y - 3, "DEMO")
    c.setFillColor(black)


def _qr(c: Canvas, payload: str, x: float, y: float) -> None:
    img = qrcode.make(payload, image_factory=qrcode.image.pil.PilImage)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    c.drawImage(ImageReader(buf), x, y, 28 * mm, 28 * mm)


def _header(c: Canvas, spec: LicenceSpec) -> float:
    title_en, title_ar, issuer = AUTHORITY_TITLE[spec.authority]
    _logo(c, 22 * mm, HEIGHT - 22 * mm)
    c.setFont("Sans-Bold", 16)
    c.drawString(36 * mm, HEIGHT - 20 * mm, title_en)
    c.setFont("Arabic", 16)
    c.drawRightString(WIDTH - 15 * mm, HEIGHT - 20 * mm, ar(title_ar))
    c.setFont("Sans", 9)
    c.drawString(36 * mm, HEIGHT - 26 * mm, issuer)
    return HEIGHT - 36 * mm


def _row(c: Canvas, y: float, key: str, value: str, arabic_value: bool = False) -> float:
    en, arabic = LABELS[key]
    c.setFont("Sans", 9)
    c.setFillColor(GREY)
    c.drawString(15 * mm, y, en)
    c.setFont("Arabic", 10)
    c.drawRightString(WIDTH - 15 * mm, y, ar(arabic))
    c.setFillColor(black)
    if arabic_value:
        c.setFont("Arabic", 11)
        c.drawString(62 * mm, y, ar(value))
    else:
        c.setFont("Sans-Bold", 10)
        c.drawString(62 * mm, y, value)
    c.setStrokeColor(LIGHT)
    c.line(15 * mm, y - 2.5 * mm, WIDTH - 15 * mm, y - 2.5 * mm)
    return y - 8 * mm


def _fields(c: Canvas, spec: LicenceSpec, y: float) -> float:
    y = _row(c, y, "licence_number", spec.printed_licence_number)
    y = _row(c, y, "trade_name_en", spec.trade_name_en)
    if spec.trade_name_ar:
        y = _row(c, y, "trade_name_ar", spec.trade_name_ar, arabic_value=True)
    y = _row(c, y, "legal_form", spec.legal_form_label_en)
    y = _row(c, y, "issue_date", _dmy(spec.issue_date))
    expiry_y = y
    y = _row(c, y, "expiry_date", _dmy(spec.expiry_date))
    if "expired_uncertain" in spec.faults:
        # An ink stamp partly covers the expiry year, so readings can disagree.
        c.saveState()
        c.setFillColor(Color(0.2, 0.25, 0.6, alpha=0.55))
        c.circle(78 * mm, expiry_y + 1 * mm, 7 * mm, stroke=0, fill=1)
        c.restoreState()
    y = _row(c, y, "establishment_date", _dmy(spec.establishment_date))
    y = _row(c, y, "chamber_number", spec.chamber_number)
    return _row(c, y, "address", spec.address)


def _activities(c: Canvas, spec: LicenceSpec, y: float) -> float:
    c.setFont("Sans-Bold", 11)
    c.drawString(15 * mm, y, "Activities")
    c.setFont("Arabic", 11)
    c.drawRightString(WIDTH - 15 * mm, y, ar("الأنشطة"))
    y -= 7 * mm
    for a in spec.activities:
        c.setFont("Sans", 10)
        c.drawString(15 * mm, y, f"{a['code']}  {a['en']}")
        c.setFont("Arabic", 10)
        c.drawRightString(WIDTH - 15 * mm, y, ar(a["ar"]))
        y -= 6 * mm
    return y - 4 * mm


def _people(c: Canvas, spec: LicenceSpec, y: float) -> float:
    c.setFont("Sans-Bold", 11)
    c.drawString(15 * mm, y, "Owners and Managers")
    c.setFont("Arabic", 11)
    c.drawRightString(WIDTH - 15 * mm, y, ar("الملاك والمديرون"))
    y -= 7 * mm
    c.setFont("Sans", 8)
    c.setFillColor(GREY)
    for x, head in ((15, "Name"), (85, "Nationality"), (135, "Role"), (165, "Share")):
        c.drawString(x * mm, y, head)
    c.setFillColor(black)
    top = y
    y -= 6 * mm
    for p in spec.people:
        c.setFont("Sans", 10)
        c.drawString(15 * mm, y, p.name)
        c.drawString(85 * mm, y, p.nationality)
        c.drawString(135 * mm, y, f"{p.role.title()} / ")
        c.setFont("Arabic", 10)
        c.drawString(
            135 * mm + c.stringWidth(f"{p.role.title()} / ", "Sans", 10), y, ar(ROLE_AR[p.role])
        )
        c.setFont("Sans", 10)
        if p.share_pct is not None:
            c.drawString(165 * mm, y, f"{p.share_pct:g}%")
        y -= 6 * mm
    if "owners_unclear" in spec.faults:
        c.setFillColor(Color(0.3, 0.3, 0.3))
        c.rect(13 * mm, y + 3 * mm, WIDTH - 26 * mm, top - y - 4 * mm, stroke=0, fill=1)
        c.setFillColor(black)
    return y - 4 * mm


def render_licence(spec: LicenceSpec) -> bytes:
    buf = io.BytesIO()
    c = _canvas(buf)
    _watermark(c)
    y = _header(c, spec)
    if spec.layout == "B":
        # Layout B: the licence number sits in a box at the top right, before the table.
        c.setStrokeColor(black)
        c.rect(WIDTH - 75 * mm, HEIGHT - 50 * mm, 60 * mm, 11 * mm)
        c.setFont("Sans", 8)
        c.drawString(WIDTH - 73 * mm, HEIGHT - 43 * mm, "Licence No / ")
        c.setFont("Arabic", 8)
        c.drawString(
            WIDTH - 73 * mm + c.stringWidth("Licence No / ", "Sans", 8),
            HEIGHT - 43 * mm,
            ar("رقم الرخصة"),
        )
        c.setFont("Sans-Bold", 11)
        c.drawString(WIDTH - 73 * mm, HEIGHT - 48 * mm, spec.printed_licence_number)
        y -= 18 * mm
    y = _fields(c, spec, y)
    y = _activities(c, spec, y - 2 * mm)
    y = _people(c, spec, y)
    for line in spec.extra_text:
        c.setFont("Sans", 7)
        c.drawString(15 * mm, max(y, 45 * mm), line)
        y -= 5 * mm
    if spec.qr_payload:
        _qr(c, spec.qr_payload, 15 * mm, 12 * mm)
    c.setFont("Sans", 7)
    c.setFillColor(GREY)
    c.drawRightString(
        WIDTH - 15 * mm, 12 * mm, "Synthetic test document. Not issued by any authority."
    )
    c.showPage()
    c.save()
    return buf.getvalue()


def render_other(kind: str, number_hint: str = "1234567") -> bytes:
    """Non-licence documents: out-of-scope and unclear cases."""
    buf = io.BytesIO()
    c = _canvas(buf)
    _watermark(c)
    _logo(c, 22 * mm, HEIGHT - 22 * mm)
    c.setFont("Sans-Bold", 15)
    y = HEIGHT - 45 * mm
    body: list[str]
    if kind == "moa":
        c.drawString(36 * mm, HEIGHT - 20 * mm, "Memorandum of Association")
        body = [
            "The parties below agree to form a limited liability company.",
            "Article 1: The capital of the company is AED 300,000.",
            "Article 2: The partners share profits in proportion to their shares.",
            f"Article 3: Registered reference {number_hint} appears in the annex.",
        ]
    elif kind == "moa_with_licence_no":
        c.drawString(36 * mm, HEIGHT - 20 * mm, "Memorandum of Association")
        body = [
            "The parties below agree to amend the company's articles.",
            f"Licence No. {number_hint}",
            "Article 1: The partners keep their current shares.",
        ]
    elif kind == "emirates_id":
        c.drawString(36 * mm, HEIGHT - 20 * mm, "Resident Identity Card")
        body = ["ID Number: 784-1990-1234567-1", "Name: Sample Holder", "Expiry: 01/01/2028"]
    elif kind == "passport":
        c.drawString(36 * mm, HEIGHT - 20 * mm, "PASSPORT")
        body = [
            "Type P   Code XXA   Passport No. X0000000",
            "Surname: SAMPLE",
            "Given names: HOLDER",
            "P<XXASAMPLE<<HOLDER<<<<<<<<<<<<<<<<<<<<<<<<",
        ]
    elif kind == "renewal_letter":
        c.drawString(36 * mm, HEIGHT - 20 * mm, "Renewal Confirmation")
        body = [
            "We confirm receipt of your renewal application.",
            f"Licence No: {number_hint}",
            "Your updated document will follow by email.",
        ]
    elif kind == "blank":
        body = []
    else:
        raise ValueError(f"unknown document kind {kind}")
    c.setFont("Sans", 11)
    for line in body:
        c.drawString(20 * mm, y, line)
        y -= 8 * mm
    c.showPage()
    c.save()
    return buf.getvalue()
