# 02 — Structured output and validation

## In one minute

Every hand-off between steps carries a typed, schema-validated object, because code reads a named field more reliably than it searches prose.

**A schema promises shape, not truth.** It guarantees that each field exists, has the right type, and takes an allowed value. It does not guarantee that the value is correct, so value checks and evidence checks come after it.

## Rules

- **Validate in four layers.** Each layer answers a different question.

  | Layer | Question |
  |---|---|
  | API (structured outputs, `strict` tools) | Is the reply the right shape? |
  | Pydantic (types, ranges, local invariants) | Are the types and local rules valid? |
  | Business rules (code) | Are the values correct? |
  | Grounding (evidence quote against OCR text) | Did the document really say this? |

- **Every closed list needs an escape value** (`unclear`, `other`, `unknown`), and every field needs a way to say `not_present`. Without them, the schema forces the model to invent an answer.
- **A list can be unreadable too.** Wrap it: use `Field[list[...]]`, not a plain list. Otherwise an unreadable owners table becomes `[]`, which reads as "no owners".
- **Code supplies what code knows:** IDs, today's date, the applicant name. The model supplies only what it must read.
- **A retry states what failed:** the field and the reason. A reply cut off at `max_tokens` needs a higher limit, not the same call again.
- **Use codes, not prose, between components.** Reasons and errors are closed enums, such as `ReasonCode` and `ErrorCode`. The UI maps each code to text, and tests assert codes.
- **Treat a schema as an interface.** Change it deliberately, because a schema change also invalidates the prompt cache.

## In this repository

- **The wrapper:** `Field[T]`, with `status`, `origin`, `evidence_quote` and `page` ([data model](../../specs/001-licence-to-kyb/data-model.md)).
- **The four layers:** [architecture §6](../architecture.md#6-schema-validation-in-four-layers).
- **The closed lists:** reason and error codes ([data model](../../specs/001-licence-to-kyb/data-model.md#reason-codes)), each mapped to one string in [UI copy](../ui-copy.md).
- **The model-call contract:** `client.beta.messages.parse()` with a Pydantic model ([model calls](../../specs/001-licence-to-kyb/contracts/model-calls.md)).
- **Generated frontend types:** they come from the backend's OpenAPI schema, so the two sides cannot drift apart silently.

## Mistakes to avoid

- **Trusting a valid object.** "It parsed" means the shape is right, nothing more.
- **Plain lists for document content.** Found in review: an unreadable owners table produced "0 beneficial owners".
- **Enums without an escape value.** Found in review: `self_confidence` and the registry tool's `authority` had none.
- **Tests that match message text.** They break on every wording change. Assert codes instead.

## Self-check

<details><summary>1. A field must hold one of 10 legal forms. What else must the enum contain, and why?</summary>

An escape value such as `other`, plus a `not_present` or `unclear` status on the field. Without them, the model must pick one of the 10 even when none fits, so the schema rewards invention.
</details>

<details><summary>2. Name the four validation layers and one failure each catches.</summary>

1. **API:** a missing field.
2. **Pydantic:** a share of 120%, or the date 31/02/2026.
3. **Business rules:** an expired licence, an expiry date before the issue date, or a wrong number format.
4. **Grounding:** a value that the document does not contain.
</details>

<details><summary>3. Why can citations not be used for evidence here?</summary>

The API cannot combine citations with structured outputs in one request. So evidence is a schema field (`evidence_quote`), and code checks it against the OCR text.
</details>
