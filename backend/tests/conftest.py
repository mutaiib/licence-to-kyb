"""Test-wide setup."""

from __future__ import annotations

import os
from pathlib import Path

# Use the repository's pinned Tesseract data when present (scripts/fetch_tessdata.sh).
_TESSDATA = Path(__file__).resolve().parents[2] / "var" / "tessdata"
if _TESSDATA.is_dir() and "TESSDATA_PREFIX" not in os.environ:
    os.environ["TESSDATA_PREFIX"] = str(_TESSDATA)
