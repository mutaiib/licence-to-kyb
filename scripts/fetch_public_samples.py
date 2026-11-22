"""Download the public sample licence for the live eval (test-cases.md; spec Assumptions).

The file is published by its company on its own website. It is downloaded at eval time,
checked against a pinned SHA-256, and never committed (see .gitignore). Only hand labels of
company-level fields are committed, in evals/cases/public/*.json.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "evals" / "cases" / "public"


def fetch(label_path: Path) -> Path:
    label = json.loads(label_path.read_text("utf-8"))
    target = ROOT / label["document"]
    if (
        target.exists()
        and hashlib.sha256(target.read_bytes()).hexdigest() == label["document_sha256"]
    ):
        return target
    url = label["document_url"]
    if not url.startswith("https://"):
        raise ValueError(f"refusing a non-HTTPS URL: {url}")
    request = urllib.request.Request(  # noqa: S310 - HTTPS enforced above, hash pinned
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; eval-fetch)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - HTTPS, pinned hash
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != label["document_sha256"]:
        raise ValueError(f"{url} changed: sha256 {digest} != pinned {label['document_sha256']}")
    target.write_bytes(data)
    return target


def main() -> int:
    for label_path in sorted(PUBLIC.glob("*.json")):
        print(f"ok {fetch(label_path).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
