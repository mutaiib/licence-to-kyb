"""Fit confidence thresholds from an eval run's signal rows (US3, T074).

    uv --project backend run python scripts/calibrate.py ROWS.jsonl

Each line of ROWS.jsonl is one field of one case:
    {"field": "expiry_date", "split": "calibration", "signals": {...}, "correct": true}
The eval runner (User Story 6) writes this file during a live run. Only calibration-split
rows are used. The result goes to backend/config/thresholds.<MODEL_PROFILE>.yaml, because
thresholds are fitted per model profile (ADR-004), with ``fitted: true`` and a fit summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from licence_kyb.calibration import SignalRow, fit_thresholds, precision_at
from licence_kyb.config import CONFIG_DIR, profile_name
from licence_kyb.nodes.confidence import load_config, weighted_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.graders import wilson_interval


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("rows", type=Path, help="JSONL signal rows from an eval run")
    parser.add_argument("--target", type=float, default=0.99, help="precision target")
    args = parser.parse_args()

    rows = [SignalRow(**json.loads(line)) for line in args.rows.read_text().splitlines() if line]
    calibration = [r for r in rows if r.split == "calibration"]
    # A fit on nothing, or on scripted readings (always right), would mean nothing.
    if not calibration:
        sys.exit("no calibration-split rows: run the eval on --split calibration first")
    if any(r.source == "scripted" for r in calibration):
        sys.exit("these rows come from the scripted model; fit only on real model readings")
    config = load_config()
    thresholds = fit_thresholds(rows, config.weights, args.target, defaults=default_thresholds())
    summary = {}
    for field, t in thresholds.items():
        passing = [r for r in calibration if r.field == field]
        precision = precision_at(calibration, config.weights, field, t)
        reached = [r for r in passing if weighted_score(r.signals, config.weights) >= t]
        low, _ = wilson_interval(sum(r.correct for r in reached), len(reached))
        summary[field] = {
            "threshold": t,
            "precision": None if precision is None else round(precision, 4),
            "wilson_95_low": round(low, 4) if reached else None,
            "rows": len(passing),
            "rows_at_or_above": len(reached),
        }
    out = {
        "fitted": True,
        "fitted_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "target_precision": args.target,
        "weights": config.weights,
        "thresholds": thresholds,
        "fit_summary": summary,
    }
    profile = profile_name()
    out["model_profile"] = profile
    (CONFIG_DIR / f"thresholds.{profile}.yaml").write_text(yaml.safe_dump(out, sort_keys=False))
    print(json.dumps(summary, indent=2))


def default_thresholds() -> dict[str, float]:
    """The configured fields and their documented default thresholds (thresholds.yaml)."""
    data = yaml.safe_load((CONFIG_DIR / "thresholds.yaml").read_text())
    return {k: float(v) for k, v in data["thresholds"].items()}


if __name__ == "__main__":
    main()
