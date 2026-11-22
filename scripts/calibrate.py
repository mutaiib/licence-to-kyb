"""Fit confidence thresholds from an eval run's signal rows (US3, T074).

    uv --project backend run python scripts/calibrate.py ROWS.jsonl

Each line of ROWS.jsonl is one field of one case:
    {"field": "expiry_date", "split": "calibration", "signals": {...}, "correct": true}
The eval runner (User Story 6) writes this file during a live run. Only calibration-split
rows are used. The result replaces backend/config/thresholds.yaml, with ``fitted: true``
and a short fit summary.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from licence_kyb.calibration import SignalRow, fit_thresholds, precision_at
from licence_kyb.config import CONFIG_DIR
from licence_kyb.nodes.confidence import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("rows", type=Path, help="JSONL signal rows from an eval run")
    parser.add_argument("--target", type=float, default=0.99, help="precision target")
    args = parser.parse_args()

    rows = [SignalRow(**json.loads(line)) for line in args.rows.read_text().splitlines() if line]
    config = load_config()
    thresholds = fit_thresholds(rows, config.weights, args.target)
    summary = {
        field: {
            "threshold": t,
            "precision": round(
                precision_at(
                    [r for r in rows if r.split == "calibration"], config.weights, field, t
                ),
                4,
            ),
            "rows": sum(1 for r in rows if r.field == field and r.split == "calibration"),
        }
        for field, t in thresholds.items()
    }
    out = {
        "fitted": True,
        "fitted_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "target_precision": args.target,
        "weights": config.weights,
        "thresholds": thresholds,
        "fit_summary": summary,
    }
    (CONFIG_DIR / "thresholds.yaml").write_text(yaml.safe_dump(out, sort_keys=False))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
