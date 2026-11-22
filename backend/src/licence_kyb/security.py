"""Encryption at rest and personal-data masking (constitution Principle VIII).

Masking applies to logs, traces and trace API responses only. It never alters the input to
extraction, which needs the real values.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from cryptography.fernet import Fernet, MultiFernet

# Field names whose values are personal data. Trade names are public and are not masked.
PII_FIELDS: frozenset[str] = frozenset(
    {
        "licence_number",
        "unified_licence_number",
        "register_number",
        "people",
        "name",
        "nationality",
        "address",
        "registered_address",
        "beneficial_owners",
        "controllers",
        "old",
        "new",
        "value",
        "read_value",
        "corrected_value",
        "applicant_name",
    }
)


class Cipher:
    """Fernet encryption with key rotation: the first key encrypts, every key decrypts."""

    def __init__(self, keys: Sequence[str]) -> None:
        if not keys:
            raise ValueError("at least one encryption key is required")
        self._fernet = MultiFernet([Fernet(k.encode()) for k in keys])

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        return self._fernet.decrypt(token)

    def encrypt_text(self, text: str) -> str:
        return self.encrypt(text.encode()).decode()

    def decrypt_text(self, token: str) -> str:
        return self.decrypt(token.encode()).decode()


def mask_value(value: Any) -> str:
    """A stable, non-reversible stand-in: equal inputs give equal masks, for debugging joins."""
    digest = hashlib.sha256(str(value).encode()).hexdigest()[:8]
    return f"<masked:{digest}>"


def masked(obj: Any, pii_fields: Iterable[str] = PII_FIELDS) -> Any:
    """Return a copy of ``obj`` with every PII-tagged field replaced, recursively."""
    fields = frozenset(pii_fields)

    def walk(node: Any) -> Any:
        if isinstance(node, Mapping):
            return {k: (_mask_tree(v) if k in fields else walk(v)) for k, v in node.items()}
        if isinstance(node, list | tuple):
            return [walk(item) for item in node]
        return node

    return walk(obj)


def _mask_tree(node: Any) -> Any:
    if isinstance(node, Mapping):
        return {k: _mask_tree(v) for k, v in node.items()}
    if isinstance(node, list | tuple):
        return [_mask_tree(item) for item in node]
    return None if node is None else mask_value(node)


class PiiMaskingFilter(logging.Filter):
    """Masks PII-tagged attributes passed through ``extra=`` before any handler formats them."""

    def filter(self, record: logging.LogRecord) -> bool:
        for name in PII_FIELDS:
            if name in record.__dict__:
                record.__dict__[name] = _mask_tree(record.__dict__[name])
        return True
