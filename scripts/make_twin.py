"""Approve a captured reviewer correction for the eval set (US6, T095; FR-033).

    make approve-capture ID=<capture_key>

The correction is marked ``approved_for_eval`` and becomes a synthetic twin: a new licence
with the same authority layout and fault group, and generated values. The twin's case file
goes to evals/cases/twins/ (committed); its PDF goes to data/generated/twins/ (regenerated
from the seed in the case file). No personal value from the real case is copied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.twins import make_twin

from licence_kyb.config import REPO_ROOT, Settings
from licence_kyb.graph import thread_config
from licence_kyb.llm.client import DailyBudget, LLMClient
from licence_kyb.pipeline import Deps, Pipeline
from licence_kyb.security import Cipher
from licence_kyb.testdata.answers import ScriptedTransport

CASES = REPO_ROOT / "evals" / "cases" / "twins"
DOCUMENTS = REPO_ROOT / "data" / "generated" / "twins"


def main() -> None:
    parser = argparse.ArgumentParser(description="Turn an approved correction into a twin.")
    parser.add_argument("capture_key")
    parser.add_argument("--seed", type=int, default=20260601)
    args = parser.parse_args()

    settings = Settings()
    cipher = Cipher([k.get_secret_value() for k in settings.fernet_keys])
    # Only stored state is read: no model is called, so the scripted client never answers.
    pipeline = Pipeline(
        Deps(
            data_dir=settings.data_dir,
            cipher=cipher,
            llm=LLMClient(ScriptedTransport(None), DailyBudget(0)),
        )
    )
    capture = pipeline.db.capture(args.capture_key)
    if capture is None:
        raise SystemExit(f"no captured correction {args.capture_key!r}")
    state = pipeline.graph.get_state(thread_config(capture["run_id"])).values
    authority = state.get("route", {}).get("authority", "unknown")
    if authority == "unknown":
        raise SystemExit("the run has no known authority, so a twin cannot copy its layout")

    case = make_twin({**capture, "authority": authority}, out_dir=DOCUMENTS, seed=args.seed)
    case["document"] = f"data/generated/twins/{case['document']}"
    CASES.mkdir(parents=True, exist_ok=True)
    (CASES / f"{case['case_id']}.json").write_text(json.dumps(case, ensure_ascii=False, indent=2))
    (DOCUMENTS / f"{case['case_id']}.json").unlink(missing_ok=True)
    pipeline.db.set_capture_status(args.capture_key, "approved_for_eval")
    print(f"twin {case['case_id']} written to {Path('evals/cases/twins')}")


if __name__ == "__main__":
    main()
