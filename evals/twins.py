"""Synthetic twins of approved reviewer corrections (US6, T095; FR-033).

A twin keeps what made the case hard (the authority's layout and the fault group) and
replaces every value with generated ones. No personal value from the real case is copied.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from licence_kyb.testdata.render import render_licence
from licence_kyb.testdata.spec import make_spec

# Fault groups that are a property of the document, and the generator fault that draws
# them. Other groups (for example evidence_mismatch) are reading faults of the model: the
# twin is then a clean document that tests the same field again.
DOCUMENT_FAULTS = {
    "expired": "expired",
    "expiry_uncertain": "expired_uncertain",
    "near_expiry": "near_expiry",
    "number_format": "wrong_number_format",
    "qr_mismatch": "qr_mismatch",
    "registry_not_found": "registry_not_found",
    "high_risk_activity": "high_risk_activity",
    "shares_total": "shares_total",
    "ubo_needs_examination": "no_shares",
    "arabic_name_missing": "arabic_name_missing",
}


def make_twin(correction: dict[str, Any], *, out_dir: Path, seed: int) -> dict[str, Any]:
    """Write the twin's PDF and case file to ``out_dir``, and return the case."""
    fault_group = str(correction["fault_group"])
    key = hashlib.sha256(str(correction["capture_key"]).encode()).hexdigest()[:8]
    case_id = f"twin_{fault_group}_{key}"
    faults = {DOCUMENT_FAULTS[fault_group]} if fault_group in DOCUMENT_FAULTS else set()
    spec = make_spec(case_id, str(correction["authority"]), "A", faults, seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{case_id}.pdf").write_bytes(render_licence(spec))
    case = {
        "case_id": case_id,
        "source": "synthetic",
        "group": "twin",
        "document": f"{case_id}.pdf",
        "mime": "application/pdf",
        "applicant_name": spec.applicant_name,
        "expected_route": ["needs_review", "reject"] if faults else ["ready", "needs_review"],
        "expected_reason_codes": [],
        "expected_values": spec.ground_truth(),
        "authority": spec.authority,
        "faults": sorted(faults),
        "fault_group": fault_group,
        "corrected_field": correction["field"],
        "split": "test",
        "mix_bucket": "problem",
        "twin_of": None,
        "seed": seed,
    }
    (out_dir / f"{case_id}.json").write_text(json.dumps(case, ensure_ascii=False, indent=2))
    return case
