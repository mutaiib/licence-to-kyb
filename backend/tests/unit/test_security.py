"""Encryption at rest and personal-data masking (constitution Principle VIII)."""

from __future__ import annotations

import io
import json
import logging

from cryptography.fernet import Fernet

from licence_kyb.security import Cipher, PiiMaskingFilter, mask_value, masked


def test_encrypted_bytes_differ_from_input_and_round_trip_exactly() -> None:
    cipher = Cipher([Fernet.generate_key().decode()])
    original = b"%PDF-1.7 trade licence bytes"

    stored = cipher.encrypt(original)

    assert stored != original
    assert original not in stored
    assert cipher.decrypt(stored) == original


def test_data_encrypted_with_an_old_key_still_decrypts_after_rotation() -> None:
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    stored = Cipher([old_key]).encrypt(b"owner: Ahmed Al Mansoori")

    rotated = Cipher([new_key, old_key])

    assert rotated.decrypt(stored) == b"owner: Ahmed Al Mansoori"
    assert Cipher([new_key]).decrypt(rotated.encrypt(b"x")) == b"x"


def test_masked_value_keeps_no_original_characters_beyond_a_short_hint() -> None:
    result = mask_value("Ahmed Al Mansoori")

    assert "Ahmed" not in result
    assert "Mansoori" not in result


def test_pii_tagged_fields_are_masked_recursively_in_trace_output() -> None:
    payload = {
        "licence_number": "1234567",
        "trade_name_en": "Acme General Trading LLC",
        "people": [{"name": "Ahmed Al Mansoori", "nationality": "United Arab Emirates"}],
        "nested": {"address": "Office 12, Deira, Dubai"},
    }

    out = json.dumps(masked(payload), ensure_ascii=False)

    for secret in ("1234567", "Ahmed Al Mansoori", "United Arab Emirates", "Deira"):
        assert secret not in out
    assert "Acme General Trading LLC" in out  # trade names are public and stay readable


def test_log_records_never_contain_pii_values_from_extra_fields() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("test.pii")
    logger.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.addFilter(PiiMaskingFilter())
    handler.setFormatter(logging.Formatter("%(message)s %(people)s %(licence_number)s"))
    logger.addHandler(handler)
    logger.propagate = False

    logger.warning(
        "extracted",
        extra={"people": [{"name": "Ahmed Al Mansoori"}], "licence_number": "1234567"},
    )

    line = stream.getvalue()
    assert "Ahmed Al Mansoori" not in line
    assert "1234567" not in line
    assert "extracted" in line
