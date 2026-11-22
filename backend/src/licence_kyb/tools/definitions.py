"""The resolver's tool definitions (contracts/resolver-tools.md, "Tools").

Each tool's arguments are a Pydantic model. The same model gives the JSON schema the model
sees (strict, no extra properties) and re-validates every call in code.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Region = Literal["top_left", "top_right", "middle", "bottom_left", "bottom_right", "full_page"]
Page = Field(ge=1, le=5)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReReadArgs(_Args):
    page: int = Page
    field: str
    region: Region


class OcrArgs(_Args):
    page: int = Page
    region: Region


class RegistryArgs(_Args):
    licence_number: str = Field(min_length=1, max_length=30)
    authority: Literal["DET", "ADDED", "DMCC", "IFZA", "unknown"]


class ActivityArgs(_Args):
    query: str = Field(min_length=1, max_length=100)


class ReportArgs(_Args):
    pass


class ProposeArgs(_Args):
    field: str
    new_value: str = Field(min_length=1, max_length=200)
    evidence_quote: str = Field(min_length=1, max_length=300)
    self_confidence: Literal["high", "medium", "low", "unknown"]
    rationale: str = Field(max_length=300)


class FinishArgs(_Args):
    summary: str = Field(max_length=500)


ARGS: dict[str, type[_Args]] = {
    "licence_reread_region": ReReadArgs,
    "licence_ocr_region": OcrArgs,
    "licence_lookup_registry": RegistryArgs,
    "licence_lookup_activity": ActivityArgs,
    "licence_get_validation_report": ReportArgs,
    "propose_fix": ProposeArgs,
    "finish": FinishArgs,
}

DESCRIPTIONS = {
    "licence_reread_region": "Re-read one region of a licence page at high resolution. Use it "
    "when a field failed the evidence check or the two readings disagree. Do not use it for "
    "fields that passed. Returns the text found, or says the region has no readable text.",
    "licence_ocr_region": "Return the OCR words and their confidence for one region. Use it to "
    "check the reading quality before you propose a value. Do not use it to search the whole "
    "document.",
    "licence_lookup_registry": "Look up a licence number in the issuing authority's public "
    "register. Use it when the licence number or expiry date is in doubt. Returns the status "
    "and expiry, or says that no record exists.",
    "licence_lookup_activity": "Search the activity catalogue by code or by words. Use it when "
    "an activity code or description is unclear. Do not use it for other fields. Returns the "
    "matching activities, or says that nothing matches.",
    "licence_get_validation_report": "Return the checks that still fail. Use it after you "
    "propose fixes to see what still fails. Do not call it twice without a new proposal in "
    "between: the result does not change.",
    "propose_fix": "Propose a corrected value for one failed field. The value is used only if "
    "every check on the field passes. Call it once per field. Write dates as DD/MM/YYYY.",
    "finish": "End the investigation. Call it after your proposals, or when nothing more can "
    "be found. Do not call other tools after it: the investigation is over.",
}


def tool_definitions(failed_fields: tuple[str, ...], *, vision: bool) -> list[dict[str, Any]]:
    """The tools offered for one run. ``field`` arguments list only the failed fields, and a
    text-only model does not get the vision re-read."""
    tools = []
    for name, model in ARGS.items():
        if name == "licence_reread_region" and not vision:
            continue
        schema = model.model_json_schema()
        if "field" in schema.get("properties", {}):
            schema["properties"]["field"] = {"type": "string", "enum": list(failed_fields)}
        schema["additionalProperties"] = False
        tools.append(
            {
                "name": name,
                "description": DESCRIPTIONS[name],
                "input_schema": schema,
                "strict": True,
            }
        )
    return tools
