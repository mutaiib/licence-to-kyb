# UX review (2026-11-22)

A review of every page at desktop (1440 px) and phone (390 px) width, with all six user
stories in place. Each finding is a task in [tasks.md](tasks.md) ("UI and UX polish"), with
a test, and is checked again in the browser after the fix.

| # | Page | Finding | Why it matters | Task |
|---|---|---|---|---|
| 1 | Review | Approve form, Submit and Reject are at the bottom, below every field | The reviewer scrolls past fields that passed to finish the job | T112 |
| 2 | Review | Flagged fields are mixed with passed fields, in form order | The reviewer's job is to examine only the flagged fields (US2) | T113 |
| 3 | Review | No business name, upload time or link to the trace | The reviewer cannot tell which application this is, or why a value was read | T114 |
| 4 | Review | Each field reason shows twice: in "Reasons" and on the field | Repeated text hides the run-level reasons that need attention | T114 |
| 5 | Review (phone) | The licence image comes after the whole form | The evidence for a flagged field is out of reach | T118 |
| 6 | Runs (phone) | The table breaks words letter by letter | The page is unreadable on a phone | T115 |
| 7 | Runs | Route and Status say the same thing; an empty list has no next step | Noise, and a dead end on first use | T115 |
| 8 | Trace | No run header and no totals | A trace is read to answer "how long, how much, which models" | T116 |
| 9 | Upload | No sentence about what happens after upload; the business-name field has no hint | First use is guesswork | T117 |
| 10 | All | No automatic accessibility check | WCAG 2.2 AA (FR-042) is not checked on each change | T098 |

## Result

All ten findings are fixed, each with a test, and checked again in the browser
(`docs/images/ui/`). The browser checks also found two more defects, now fixed:

- The trace showed only the steps that call a model; FR-032 asks for every step.
- A `ready` run offered Submit before anyone approved the form, so Submit failed. The run
  view now says whether the current form version is approved (`form_approved`).

Accessibility (T098): axe-core finds no WCAG 2.2 AA problem on any page, both in the test
suite (jsdom) and in the browser with colour contrast. A keyboard-only pass of the review
page reaches every control in working order, with a visible focus outline.
