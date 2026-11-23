"""Trace one licence through the real pipeline and write docs/walkthrough.md with images.

    make walkthrough      (or: uv --project backend run python scripts/walkthrough.py)

Every step runs the real code: intake, page reading, the rules, the resolver's tools,
confidence, the gate, the form, the review actions, submit and read-back. Only the model
calls are scripted (the `demo` profile, model `demo-labels`), so the page is the same on
every machine and costs nothing. The scripted model misreads the expiry year on purpose, so
the walkthrough shows how the checks and the resolver deal with a misreading.

The page is written from the run's real outputs, so it cannot drift from the code.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

os.environ["MODEL_PROFILE"] = "demo"  # before the pipeline reads its configuration

from cryptography.fernet import Fernet
from PIL import Image, ImageDraw

from licence_kyb.api.views import build_run_view
from licence_kyb.clock import FixedClock
from licence_kyb.graph import thread_config
from licence_kyb.llm.client import DailyBudget, LLMClient, ModelRequest, ModelResponse, Usage
from licence_kyb.nodes.intake import sniff
from licence_kyb.nodes.preprocess import Word, preprocess_file, visual_rows
from licence_kyb.pipeline import Deps, Pipeline
from licence_kyb.registry import MockRegistry
from licence_kyb.security import Cipher
from licence_kyb.testdata.answers import ScriptedTransport, dmy
from licence_kyb.tools.regions import REGIONS

ROOT = Path(__file__).resolve().parents[1]
CASE = "near_expiry_001"  # a synthetic DET licence that expires 10 days after "today"
SCAN = "scans_001"  # a photographed licence: no text layer, so Tesseract reads it
OUT = ROOT / "docs" / "walkthrough.md"
IMAGES = ROOT / "docs" / "images" / "walkthrough"
REVIEWER = "reviewer1"
HIGH, LOW = 0.9, 0.6  # OCR confidence bands for the box colours
GREEN, ORANGE, RED = (22, 163, 74), (217, 119, 6), (220, 38, 38)
SIGNALS = ("agreement", "grounding", "rules", "ocr", "corroboration", "self_rating")
SHOWN_FIELDS = ("licence_number", "trade_name_en", "legal_form", "expiry_date")
AUDIT_MEANING = {
    "status_change": "processing ended; the run waits for a person",
    "approve": "the reviewer approved one flagged field",
    "approve_form": "the reviewer approved this form version",
    "submit": "the form was stored once",
    "verify": "the stored record was read back and matched",
}


# ------------------------------------------------------------------ the scripted model
class WalkthroughModel(ScriptedTransport):
    """Answers from the case labels, except that the first reading gets the expiry year
    wrong. The resolver then reads one region with a real tool and proposes the fix.
    Every request and reply is kept for the page."""

    def __init__(self, labels: dict[str, Any], expiry_region: str) -> None:
        super().__init__(labels)
        self.truth = labels["expiry_date"]
        self.expiry_region = expiry_region
        self.exchanges: list[dict[str, Any]] = []
        self.resolver_turns = 0

    def send(self, req: ModelRequest) -> ModelResponse:
        if req.step == "extract_primary":
            misread = {**(self.labels or {}), "expiry_date": wrong_year(self.truth)}
            reply = ScriptedTransport(misread).send(req)
        elif req.step == "resolve":
            reply = self._resolver_turn(req)
        else:
            reply = super().send(req)
        self.exchanges.append({"request": req, "reply": reply})
        return reply

    def _resolver_turn(self, req: ModelRequest) -> ModelResponse:
        self.resolver_turns += 1
        if self.resolver_turns == 1:
            blocks = [tool_use("licence_ocr_region", page=1, region=self.expiry_region)]
        else:
            date = dmy(self.truth)
            reason = f"The OCR text of the {self.expiry_region} region shows a different year."
            blocks = [
                tool_use(
                    "propose_fix",
                    field="expiry_date",
                    new_value=date,
                    evidence_quote=f"Expiry Date {date}",
                    self_confidence="high",
                    rationale=reason,
                ),
                tool_use("finish", summary="Corrected the expiry year from the OCR text."),
            ]
        return ModelResponse(
            content=blocks,
            parsed=None,
            stop_reason="tool_use",
            serving_model=req.model,
            usage=Usage(),
        )


def tool_use(name: str, **arguments: Any) -> dict[str, Any]:
    return {"type": "tool_use", "id": f"t-{uuid.uuid4().hex[:6]}", "name": name, "input": arguments}


def wrong_year(iso: str) -> str:
    return str(int(iso[:4]) + 2) + iso[4:]


# ------------------------------------------------------------------ running the licence
def run() -> dict[str, Any]:
    case = json.loads((ROOT / "evals" / "cases" / "synthetic" / f"{CASE}.json").read_text())
    data = (ROOT / case["document"]).read_bytes()
    model = WalkthroughModel(case["expected_values"], region_of(data, case))
    pipeline = Pipeline(
        Deps(
            data_dir=Path(tempfile.mkdtemp(prefix="walkthrough-")),
            cipher=Cipher([Fernet.generate_key().decode()]),
            llm=LLMClient(model, DailyBudget(10**9)),
            clock=FixedClock(),
            registry=MockRegistry(ROOT / "data" / "registry_mock.json"),
        )
    )
    upload = pipeline.upload(data, applicant_name=case["applicant_name"])
    run_id = upload.run_id
    assert run_id is not None  # noqa: S101 - the synthetic licence passes intake
    state = pipeline.process(run_id)
    snapshots = pipeline.graph.get_state_history(thread_config(run_id))
    history = [s.values for s in reversed(list(snapshots))]
    view = build_run_view(pipeline, run_id)
    review = act_as_reviewer(pipeline, run_id, state)
    return {
        "case": case,
        "data": data,
        "upload": upload,
        "pipeline": pipeline,
        "run_id": run_id,
        "state": state,
        "history": history,
        "model": model,
        "view": view,
        "review": review,
    }


def region_of(data: bytes, case: dict[str, Any]) -> str:
    """The page region (tools/regions.py) that holds the printed expiry date."""
    date = dmy(case["expected_values"]["expiry_date"])
    word = next(w for w in preprocess_file(data, "application/pdf").words if w.text == date)
    cx, cy = (word.bbox[0] + word.bbox[2]) / 2, (word.bbox[1] + word.bbox[3]) / 2
    return next(
        name
        for name, (x0, y0, x1, y1) in REGIONS.items()
        if name != "full_page" and x0 <= cx <= x1 and y0 <= cy <= y1
    )


def act_as_reviewer(pipeline: Pipeline, run_id: str, state: dict[str, Any]) -> dict[str, Any]:
    """Approve the flagged field, approve the form, submit: what a person does on the page."""
    flagged = [f for f, s in state["form"]["field_states"].items() if s == "needs_examination"]
    decisions = [
        {"decision_id": str(uuid.uuid4()), "field": f, "action": "approve"} for f in flagged
    ]
    pipeline.act(run_id, review_action(state["form"]["version"], decisions))
    version = pipeline.state(run_id)["form"]["version"]
    pipeline.act(run_id, review_action(version, [], approve_form=True))
    version = pipeline.state(run_id)["form"]["version"]
    submit = {
        "kind": "submit",
        "action_id": str(uuid.uuid4()),
        "form_version": version,
        "reviewer": REVIEWER,
    }
    final = pipeline.act(run_id, submit)
    return {"flagged": flagged, "final": final, "audit": pipeline.db.audit_events(run_id)}


def review_action(version: int, decisions: list[dict[str, Any]], **form: Any) -> dict[str, Any]:
    return {
        "kind": "review",
        "action_id": str(uuid.uuid4()),
        "reviewer": REVIEWER,
        "form_version": version,
        "decisions": decisions,
        **form,
    }


# ------------------------------------------------------------------ images
def draw_words(img: Image.Image, words: list[Word], highlight: Any = None) -> Image.Image:
    """Every word's box, coloured by OCR confidence; the evidence box in red."""
    out = img.copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size
    for word in words:
        x0, y0, x1, y1 = word.bbox
        colour = GREEN if word.conf >= HIGH else ORANGE if word.conf >= LOW else RED
        draw.rectangle((x0 * w, y0 * h, x1 * w, y1 * h), outline=colour, width=2)
    if highlight is not None:
        x0, y0 = highlight.x * w - 6, highlight.y * h - 6
        x1, y1 = (highlight.x + highlight.w) * w + 6, (highlight.y + highlight.h) * h + 6
        draw.rectangle((x0, y0, x1, y1), outline=RED, width=5)
    return out


def save(img: Image.Image, name: str, width: int = 900) -> str:
    IMAGES.mkdir(parents=True, exist_ok=True)
    img.resize((width, round(img.height * width / img.width))).save(IMAGES / name, optimize=True)
    return f"images/walkthrough/{name}"


def png(data: bytes) -> Image.Image:
    return Image.open(BytesIO(data)).convert("RGB")


# ------------------------------------------------------------------ text helpers
def code(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n```"


def excerpt(text: str, needle: str, around: int = 160) -> str:
    """The part of a long tool result around ``needle``."""
    i = text.find(needle)
    start, end = max(0, i - around), min(len(text), i + len(needle) + around)
    return ("… " if start else "") + text[start:end] + (" …" if end < len(text) else "")


def failing_rows(results: list[dict[str, Any]]) -> str:
    rows = [
        f"| `{r['rule_id']}` | {', '.join(r['fields'])} | {r['severity']} | `{r['reason_code']}` |"
        for r in results
        if r["outcome"] == "failed"
    ]
    return "| Rule | Field | Severity | Reason |\n|---|---|---|---|\n" + "\n".join(rows)


def confidence_rows(confidence: dict[str, Any]) -> str:
    """One row per shown field; "—" for a signal the field has no evidence of."""
    lines = [
        "| Field | " + " | ".join(SIGNALS) + " | **Score** | Threshold |",
        "|---" * (len(SIGNALS) + 3) + "|",
    ]
    for name in SHOWN_FIELDS:
        c = confidence[name]
        cells = [f"{c['signals'][s]:.2f}" if s in c["signals"] else "—" for s in SIGNALS]
        score = f"**{c['score']:.2f}**"
        lines.append(f"| `{name}` | " + " | ".join(cells) + f" | {score} | {c['threshold']} |")
    return "\n".join(lines)


def field_of(parsed: dict[str, Any], name: str) -> dict[str, Any]:
    f = parsed[name]
    return {k: f.get(k) for k in ("value", "status", "evidence_quote", "page")}


def first_rule_results(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rule results of the first validate, before the resolver changed anything."""
    results: list[dict[str, Any]] = next(s for s in history if s.get("rule_results"))[
        "rule_results"
    ]
    return results


# ------------------------------------------------------------------ the page
def facts(r: dict[str, Any]) -> dict[str, Any]:
    """Every value the page shows, computed once, so the template stays short."""
    case, state, review = r["case"], r["state"], r["review"]
    words = [Word.from_dict(w) for w in state["pages"]["words"]]
    page = png(r["pipeline"].page_png(r["run_id"], 1))
    expiry_box = r["view"].form.fields["expiry_date"].evidence_box
    scan_file = ROOT / "data" / "generated" / f"{SCAN}.jpg"
    scan = preprocess_file(scan_file.read_bytes(), "image/jpeg")
    calls = {c["request"].step: c for c in r["model"].exchanges}
    resolver = [c for c in r["model"].exchanges if c["request"].step == "resolve"]
    tool_result = next(
        block
        for c in resolver
        for m in c["request"].messages
        for block in m["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
    )
    truth = case["expected_values"]["expiry_date"]
    number_word = next(w for w in words if w.text == case["expected_values"]["licence_number"])
    primary = calls["extract_primary"]["reply"].parsed
    secondary = calls["extract_secondary"]["reply"].parsed
    first_results = first_rule_results(r["history"])
    documents = {d["document"].replace("_", " ") for d in state["form"]["required_documents"]}
    final = review["final"]
    return {
        "document": case["document"],
        "authority": case["authority"],
        "today": FixedClock().today(),
        "mime": sniff(r["data"]),
        "size": f"{len(r['data']):,}",
        "pages": r["upload"].page_count,
        "run": r["run_id"][:8],
        "page_png": save(page, "1-page.png"),
        "words_png": save(draw_words(page, words, expiry_box), "2-words-and-evidence.png"),
        "scan_png": save(draw_words(png(scan.images[0]), scan.words), "3-scan-ocr.png"),
        "width": page.width,
        "height": page.height,
        "source": state["pages"]["source"],
        "word_count": len(words),
        "qr": state["pages"]["qr_payload"],
        "rows": "\n".join(" ".join(w.text for w in row) for row in visual_rows(words)[:8]),
        "word": code(
            {
                "page": number_word.page,
                "text": number_word.text,
                "bbox": [round(v, 4) for v in number_word.bbox],
                "conf": number_word.conf,
            }
        ),
        "scan_words": len(scan.words),
        "scan_mean": sum(w.conf for w in scan.words) / len(scan.words),
        "scan_low": sum(1 for w in scan.words if w.conf < LOW),
        "route": code(calls["route"]["reply"].parsed),
        "doc_type": state["route"]["doc_type"],
        "primary": code(
            {
                "licence_number": field_of(primary, "licence_number"),
                "expiry_date": field_of(primary, "expiry_date"),
            }
        ),
        "secondary": code({"expiry_date": field_of(secondary, "expiry_date")}),
        "rule_count": len(first_results),
        "failed_first": failing_rows(first_results),
        "misread": wrong_year(truth),
        "printed": dmy(truth),
        "tools": ", ".join(f"`{t['name']}`" for t in resolver[0]["request"].tools),
        "tool_count": len(resolver[0]["request"].tools),
        "region": r["model"].expiry_region,
        "tool_text": excerpt(str(tool_result.get("content")), dmy(truth)),
        "proposal": code({k: v for k, v in state["proposals"][0].items() if k != "accepted"}),
        "accepted": state["proposals"][0]["accepted"],
        "failed_final": failing_rows(state["rule_results"]),
        "confidence": confidence_rows(state["confidence"]),
        "expiry_score": state["confidence"]["expiry_date"]["score"],
        "route_name": state["decision"]["route"],
        "reasons": ", ".join(f"`{x['code']}`" for x in state["reasons"]),
        "passed": sum(1 for s in state["form"]["field_states"].values() if s == "passed"),
        "flagged": ", ".join(f"`{f}`" for f in review["flagged"]),
        "documents": ", ".join(sorted(documents)),
        "status": final["status"],
        "verified": final["submission"]["verified"],
        "audit": "\n".join(
            f"| {e['seq']} | {e['action']} | {e['actor']} | {AUDIT_MEANING.get(e['action'], '')} |"
            for e in review["audit"]
        ),
    }


PAGE = """# Walkthrough: one licence, start to finish

This page follows one synthetic licence through the real system. `make walkthrough`
([`scripts/walkthrough.py`](../scripts/walkthrough.py)) writes it from an actual run, so
every number, text and image below is the code's own output.

> **What is real and what is scripted.** Every step runs the real code: intake, page
> reading, the rules, the resolver's tools, confidence, the gate, the form, the review
> actions, submit and read-back. Only the **model calls are scripted** (the `demo` profile,
> model `demo-labels`): they answer from the licence's labels, so the page is the same on
> every machine and costs nothing. To show how the system deals with a misreading, the
> scripted model **reads the expiry year wrong** in its first reading.

**The licence:** `{document}`, a synthetic {authority} licence that expires 10 days after
"today" (the clock is fixed at {today} for tests and demos).

![The licence page]({page_png})

## 1. Intake: check the file before any work

Plain code, no model ([`nodes/intake.py`](../backend/src/licence_kyb/nodes/intake.py)).

| Check | Result |
|---|---|
| File type, from its first bytes (not its name) | `{mime}` |
| Size (limit 10 MB) | {size} bytes |
| Pages (limit 5) | {pages} |
| Seen before? (SHA-256 of the bytes) | no: a new run, `{run}…` |
| Stored | encrypted (Fernet); nothing is kept in plain text |

## 2. Read the pages, in a separate, limited process

The upload is untrusted: a small PDF can inflate to gigabytes. A child process reads it,
with a memory and time limit (1 GB, 60 s); a file past either is rejected
([`nodes/isolate.py`](../backend/src/licence_kyb/nodes/isolate.py),
[`nodes/preprocess.py`](../backend/src/licence_kyb/nodes/preprocess.py)).

1. **Render** each page to an image at 200 DPI ({width} by {height} pixels). The model sees
   these images, the QR decoder scans them, and the review page shows them.
2. **Get the words.** This PDF has a **text layer**, so its words come from it directly:
   exact text, confidence 1.0. Source: `{source}`, **{word_count} words**. (A scan has no
   text layer; then Tesseract reads the image, in English and Arabic: see the box below.)
3. **Keep each word's box** on the page. A PDF lists words in drawing order, which can split
   a label from its value, so code regroups them into visual rows, read left to right.
4. **Decode the QR code**, as untrusted text that is never opened: `{qr}`.

The words and their boxes. The red box is the evidence for the expiry date (steps 5 and 6).
The single letters on the diagonal are the "SPECIMEN — SYNTHETIC" watermark: words too.

![Every word's box, and the evidence box]({words_png})

The text the model receives (the first 8 visual rows):

```text
{rows}
```

**The Arabic looks backwards, and that is expected.** This PDF stores Arabic in visual order
(drawn left to right) with "presentation form" letters. The evidence check normalises the
letters (Unicode NFKC) and compares each quote with the text both ways
([`rules/grounding.py`](../backend/src/licence_kyb/rules/grounding.py)).

One word, as stored. The box is (left, top, right, bottom), as fractions of the page:

{word}

> **A scan instead of a PDF.** `{scan_name}.jpg` is a photographed copy with no text layer,
> so Tesseract reads it: **{scan_words} words**, mean confidence **{scan_mean:.2f}**,
> **{scan_low}** below 0.6. Green: at least 0.9; orange: 0.6 to 0.9; red: below 0.6.
> The bold values read well; the faint grey labels and much of the Arabic do not. That is
> why each field's confidence includes the OCR confidence of the words its quote came from.
>
> ![Tesseract's words on a scan, coloured by confidence]({scan_png})

## 3. Route: what document is this? (model, no tools)

The model gets page 1 and the first 1,500 characters of the text. Its prompt says that the
document's text is data, never instructions. Its answer (scripted here):

{route}

Code then checks the answer against the page: the licence number in the text has the
{authority} number format, so the authority stands. Result: `{doc_type}`, `{authority}`.

## 4. Extract: read the fields, then the key fields again (model, no tools)

**The first reading** fills the whole schema. Each value carries the exact text it was read
from (`evidence_quote`). Here it **misreads the expiry year**:

{primary}

**The second reading** is a separate call that reads only the critical fields. It reads the
expiry date right:

{secondary}

The two readings **disagree** on the expiry date, so their agreement is no evidence for it.

## 5. Validate: run every rule (code)

{rule_count} rule results. The ones that failed:

{failed_first}

- `evidence`: the value says {misread}, but its own quote says `Expiry Date {printed}`.
  Dates must match the text exactly.
- `registry`: the (mock) register holds a different expiry date.

A re-read can fix both, so the resolver runs.

## 6. Resolve: the one agent (model with read-only tools)

The resolver gets the failed fields and {tool_count} tools ({tools}). The `field` argument
lists only the fields that failed. Its turns (the decisions are scripted; **the tools are
real**):

1. It calls `licence_ocr_region` on the `{region}` region of page 1, where the expiry date
   is printed. **The real tool runs.** Its answer, in words (an excerpt):

   ```text
   {tool_text}
   ```

2. It proposes a fix, with the quote it read, and finishes:

{proposal}

**The agent never applies a value.** Code runs every rule on the proposal: the evidence and
the registry now agree, so the fix is accepted (`{accepted}`). Neither reading saw the new
value, so their agreement for this field is reset.

## 7. Validate again, then score confidence (code)

The evidence and registry checks now pass. One rule still fails, by design:

{failed_final}

**Confidence** combines six signals, weighted: agreement 3, grounding 3, rules 2,
corroboration 2, OCR 1, the model's own rating 0.5.

{confidence}

"—" means there is no evidence of that kind for the field (for example, the register holds
no trade name). It does not count, so it does not lower the score. The expiry date scores
{expiry_score:.2f}, below its threshold: the two readings no longer agree on it, so it goes
to a person even after the fix.

## 8. Gate: pick the route (code)

Route: **`{route_name}`**. Reasons: {reasons}. A licence that expires in 10 days needs a
person's decision; a licence whose expiry is confirmed in the past would be rejected.

## 9. The KYB form, and the documents to request (code)

{passed} fields passed; one needs a decision: {flagged}.
Documents to request: {documents}.

The run now **pauses** (LangGraph `interrupt`): its state is saved, and it survives a restart.

## 10. A person decides (the review page)

![The review page for a near-expiry licence](images/ui/review-desktop.png)

The reviewer approves the flagged field, approves the form (the approval holds for this exact
form version only), and submits. Each click is checked first, and every write is keyed, so a
repeated click writes nothing new.

## 11. Submit, read back, done (code)

The form is stored once, **read back and compared** with the approved form, and only then is
the run done. Final status: **`{status}`**. Submission verified: `{verified}`.

The audit trail (values and reasons are stored encrypted):

| # | Action | By | Meaning |
|---|---|---|---|
{audit}

## What to take away

- **The model reads; code decides.** Three steps call a model; every check, score, route and
  write is plain code.
- **The text on the page is evidence, not only input.** Every value must quote it exactly,
  and that is what caught the misread year.
- **The agent proposes; the rules accept.** The resolver used a real, read-only tool and could
  not apply its own fix.
- **A person still decides what matters.** A fixed value that the two readings did not agree
  on, and a licence close to expiry, both go to a reviewer.

See also: [architecture](architecture.md) (the diagrams), [glossary](glossary.md),
[reference](reference.md) (rules and reason codes), [status](status.md).
"""


def main() -> None:
    result = run()
    OUT.write_text(PAGE.format(scan_name=SCAN, **facts(result)))
    print(f"wrote {OUT.relative_to(ROOT)} and {len(list(IMAGES.glob('*.png')))} images")


if __name__ == "__main__":  # the page-reading child process re-imports this file
    main()
