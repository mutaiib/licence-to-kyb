"""Generate the synthetic licence catalogue (test-cases.md; research R9a).

Usage: uv --project backend run python scripts/gen_licences.py [--seed N]

Writes documents to data/generated/ (gitignored), labelled cases to evals/cases/synthetic/
and the mock registry to data/registry_mock.json. The same seed always gives the same output.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from licence_kyb.testdata.catalogue import build

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260601)
    args = parser.parse_args()
    result = build(ROOT, seed=args.seed)
    print(
        f"wrote {len(result.cases)} cases and {sum(map(len, result.registry.values()))} registry entries"
    )


if __name__ == "__main__":
    main()
