"""A hostile file costs one child process, never the service (security review, round 2)."""

from __future__ import annotations

import zlib
from pathlib import Path

from licence_kyb.testdata.answers import ScriptedTransport
from tests.builders import make_pipeline


def inflating_pdf(megabytes: int) -> bytes:
    """A one-page PDF of about 2 KB whose page content inflates to ``megabytes`` of spaces
    (Flate-compressed twice). It passes the intake checks: one page, a normal page size."""
    once = zlib.compressobj(9)
    body = b"".join(once.compress(b" " * (1 << 20)) for _ in range(megabytes)) + once.flush()
    body = zlib.compress(body, 9)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R >>",
        b"<< /Length %d /Filter [/FlateDecode /FlateDecode] >>\nstream\n" % len(body)
        + body
        + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 5\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


def test_a_file_that_inflates_past_the_memory_limit_is_rejected_as_unreadable(
    tmp_path: Path,
) -> None:
    (tmp_path / "registry.json").write_text("{}")
    pipeline = make_pipeline(
        tmp_path / "var", ScriptedTransport(None), registry_path=tmp_path / "registry.json"
    )
    pipeline.deps.page_reading_limits = (300, 60)  # MB, seconds: small, so the test is quick
    upload = pipeline.upload(inflating_pdf(400), applicant_name="Acme Trading LLC")
    assert upload.run_id is not None  # it passes intake

    state = pipeline.process(upload.run_id)

    assert state["decision"]["route"] == "reject"
    assert "unreadable_file" in {r["code"] for r in state["reasons"]}
