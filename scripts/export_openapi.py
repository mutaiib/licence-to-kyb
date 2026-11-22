"""Export the API's OpenAPI schema for frontend type generation (contracts/http-api.md).

Usage: uv --project backend run python scripts/export_openapi.py [out.json]
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from licence_kyb.api.app import create_app
from licence_kyb.config import Settings


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("var/openapi.json")
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(data_dir=Path(tmp), settings=Settings(_env_file=None))  # type: ignore[call-arg]
        schema = app.openapi()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", "utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
