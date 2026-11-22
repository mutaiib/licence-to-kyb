# Problem statement

## Who has the problem

- **Onboarding and compliance operators** at a payment provider in the UAE. They approve merchants before those merchants can accept payments.
- **Merchants** who apply. They wait while an operator checks their documents.

## The problem

Every merchant uploads a **trade licence**. An operator reads it and types 15 to 25 fields into a KYB (Know Your Business) onboarding form.

This is slow and error-prone because:

1. **Layouts differ by authority.** The UAE has more than 40 licence-issuing authorities. The Dubai mainland authority (DET), Abu Dhabi (ADDED), and the free zones (DMCC, IFZA, JAFZA, RAKEZ and others) each use their own layout and number format.
2. **Licences are bilingual.** Most licences show English and Arabic. Some fields appear only in Arabic.
3. **Quality varies.** Uploads include clean PDFs, scans and phone photos.
4. **Formats vary.** Activity codes are written in different ways (`7490.88`, `6419001.1`, `8620010`). A licence number, a register number and a Dubai Unified Licence number are different identifiers that look alike.
5. **Errors cost money in both directions.**
   - A wrong licence number or expiry date can onboard an expired or ineligible business. That is a compliance breach.
   - A false rejection loses a legitimate merchant.
6. **Manual review gets less careful over time.** When most cases are correct, reviewers start approving without reading.

## Goal

Turn one uploaded trade licence into a **validated, pre-filled KYB form that is ready to submit**. A person is involved only where the system cannot show that a value is correct, and a person always clicks Submit.

## Inputs

- One file: PDF, JPG or PNG, at most 10 MB and 5 pages.
- Applicant context: the business name on the application.

## Outputs

1. A `TradeLicenceExtraction`. Every field has a value, an evidence quote, a page, a status (`present`, `not_present`, `unclear`) and a confidence score.
2. A list of rule results.
3. A route: `ready`, `needs_review` or `reject`, with reason codes. Automatic rejection needs a corroborated value, and a person can reopen a rejected run.
4. A pre-filled `KYBOnboardingForm` and a list of documents still required.
5. An audit log of every approval, correction and submission.

## Done condition

**A run is done when all of these facts are true in stored state.** What the model says does not count.

- A `Submission` record exists, and its values equal the approved form.
- Every required field was either approved by a person or passed every check above its threshold.
- The audit log names the person who approved the submission.

## Scope

**In scope:**
- UAE trade licences from four authority profiles: **DET, ADDED, DMCC, IFZA**. A generic profile handles any other authority and always routes to review.
- English and Arabic text.
- These rules:
  - expiry date
  - licence number format for each authority
  - date logic
  - ownership share totals and the 25% beneficial-owner threshold
  - allowed legal forms
  - required Arabic name
  - high-risk activities
  - mismatch with the applicant's claimed name
  - QR payload compared with the extracted values
  - lookup in a mock registry
- A web page for review and submission.
- An eval suite of labelled cases.

**Out of scope:**
- Extracting data from MOAs, Emirates IDs or passports. The router identifies them and routes them out of scope.
- Integration with real government registries. A mock stands in for them.
- Sending submissions to a real KYB provider.
- Multi-tenant accounts and production deployment.

## Constraints

- **The uploaded document is untrusted input.** Text on the document must not change what the system does.
- **Personal data** (owner names, nationalities, licence numbers) is encrypted at rest, masked in logs and traces, and deleted after a retention period.
- **Submission always needs a person.**

## Success measures

The eval suite measures these. The README reports the measured values, including any that miss the target.

| Measure | Target |
|---|---|
| Field accuracy, clean documents | ≥ 95% |
| Field accuracy, noisy scans and photos | ≥ 85% |
| Precision of `ready` (no wrong critical field) | ≥ 99% |
| Share of documents routed to review, realistic mix | ≤ 40% |
| Seeded bad documents caught (expired, mismatch, injected text, wrong document type) | 100% |
| Cost per document (average, measured, including thinking tokens) | < $0.40 |
| Latency per document, p95, excluding human time | < 60 s without re-reading, < 90 s with it |

The [feature spec](../specs/001-licence-to-kyb/spec.md#success-criteria-mandatory) is the normative list of targets, and it adds the reviewer-time, audit and copy targets. This table is a summary.

## Why this problem

The workflow is small enough to build completely, and it contains every hard part of a real document agent:

- unstructured input
- a strict output schema
- business rules
- a confidence threshold
- a human-review step
- an untrusted-input boundary
- an eval suite that measures each part
