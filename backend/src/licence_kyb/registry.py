"""Mock authority register (spec Assumptions): DET, ADDED and DMCC; no IFZA in the demo.

Same inputs and outputs as a real register lookup. ``unavailable`` simulates an outage so
the ``could_not_run`` path can be tested and demonstrated.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from licence_kyb.config import DATA_DIR
from licence_kyb.rules.base import RegistryResult

DEFAULT_PATH = DATA_DIR / "registry_mock.json"


class RegistryUnavailableError(Exception):
    """The register did not answer."""


class MockRegistry:
    def __init__(self, path: Path = DEFAULT_PATH, *, unavailable: bool = False) -> None:
        self.records: dict[str, dict[str, dict[str, str]]] = (
            json.loads(path.read_text("utf-8")) if path.exists() else {}
        )
        self.unavailable = unavailable

    def lookup(self, number: str, authority: str) -> RegistryResult:
        if self.unavailable:
            raise RegistryUnavailableError(authority)
        record = self.records.get(authority, {}).get(number)
        if record is None:
            return RegistryResult(found=False)
        return RegistryResult(
            found=True,
            status=record.get("status"),
            expiry_date=date.fromisoformat(record["expiry_date"])
            if record.get("expiry_date")
            else None,
            trade_name_en=record.get("trade_name_en"),
        )
