"""licence_lookup_registry: look up a licence in the issuing authority's register (mock)."""

from __future__ import annotations

from licence_kyb.profiles import load_profile
from licence_kyb.registry import RegistryUnavailableError
from licence_kyb.tools import ToolContext
from licence_kyb.tools.errors import ToolResult, answer, tool_error

RETRIES = 2  # code retries temporary failures before the model sees an error


def run(ctx: ToolContext, licence_number: str, authority: str) -> ToolResult:
    if authority == "unknown" or not load_profile(authority).has_register:
        return tool_error(
            "registry_not_applicable",
            what_failed=f"licence_lookup_registry for {authority}",
            why=f"The register for {authority} is not available in this deployment.",
            state="The registry check is not applicable.",
            next_action=f"Do not call licence_lookup_registry again for {authority}.",
            is_error=False,
        )
    for attempt in range(RETRIES + 1):
        try:
            record = ctx.registry(licence_number, authority)
            break
        except RegistryUnavailableError:
            if attempt == RETRIES:
                return tool_error(
                    "registry_unavailable",
                    what_failed=f"licence_lookup_registry for licence {licence_number}, "
                    f"authority {authority}",
                    why=f"The {authority} register did not answer after {RETRIES} retries.",
                    state="Nothing changed. The registry check is now could_not_run.",
                    next_action="Do not call licence_lookup_registry again in this run. Use "
                    "the document evidence, and set self_confidence to low in a proposal.",
                )
    if not record.found:
        return answer(
            f"Registry {authority}: no record for licence {licence_number}. Check "
            "the number against the QR code and the printed text."
        )
    expiry = record.expiry_date.strftime("%d/%m/%Y") if record.expiry_date else "not given"
    return answer(
        f"Registry {authority}: licence {licence_number} is {record.status}. Expiry {expiry}."
    )
