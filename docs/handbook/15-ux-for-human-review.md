# 15 — UX for human review

## In one minute

A review screen exists so that a person decides quickly and well. Put the decision first: what this case is, what state it is in, what still needs a decision, and the buttons that finish the job. Everything that passed is one click away, not in the way.

## Rules

- **Lead with the case and its state.** The business name, when it was uploaded, the route (ready, needs examination, rejected) and a link to how the system got there.
- **Show one next step, with at most one main button.** A card at the top says what to do now: "Examine 1 flagged field", then "Approve the form" with its button, then "Submit the form" with its button. Never show buttons that are disabled for a reason the reviewer must guess; show the step that removes the reason.
- **Put the exception last.** "Reject case" is a quiet button at the end of the panel, with a reason and a confirmation. Next to Approve, in red, it looks like a normal next step.
- **Keep engineering detail one click away.** Reading confidence and weak evidence sit in a closed "Details" section under the field's buttons. The reason, the value and the text on the licence are what a reviewer decides on.
- **Show the fields to examine first.** Flagged fields open; passed fields in a closed group. The reviewer's job is the exceptions.
- **Say each reason once, where it applies.** A field's reason shows on the field; the run-level list holds only reasons about the whole case.
- **Put the evidence next to the decision.** Highlight the source text on the page image when a field is selected. On a phone, show the page right after the fields to examine.
- **Never offer an action that will fail.** If Submit needs an approval of this exact form version, the page must know whether that approval exists, and ask for it first.
- **Label model output as model output.** An explanation from the model is marked, and the page says whether the system used its value.
- **Design for phones and keyboards from the start.** Tables become lists on narrow screens; every control is reachable by keyboard with a visible focus; status is shown by text and icon, never by colour alone.
- **Check it automatically and by eye.** An automatic accessibility check (axe-core) runs on every page in the test suite; a browser pass at two widths finds what tests cannot.

## In this project

| What | Where |
|---|---|
| The UX review and what changed | `specs/001-licence-to-kyb/ux-review.md` |
| Review page: header, actions first, two field groups | `frontend/src/pages/ReviewPage.tsx`, `frontend/src/components/FormActions.tsx` |
| Runs as a list on a phone | `frontend/src/pages/RunsPage.tsx` |
| Accessibility tests (axe-core, WCAG 2.2 AA) | `frontend/tests/ux_polish.test.tsx` |
| Browser checks at desktop and phone width | `scripts/browser_check.sh` |
| Interface text in ASD-STE100 | `docs/ui-copy.md`, `scripts/lint_copy.py` |

## Self-check

<details><summary>1. The form has 12 fields; 1 is flagged. In what order should the screen show them?</summary>

The next step first ("Examine 1 flagged field"), then "Fields to examine (1)" with the flagged field open, then "Fields that passed (11)" closed, then the documents to request, and "Reject case" last.
</details>

<details><summary>2. A ready run shows "Submit" enabled. Is that correct?</summary>

Only if a reviewer approved this exact form version. A ready run still needs an approval and a click; the page must ask for the approval first, or Submit fails.
</details>

<details><summary>3. Why test accessibility in the test suite and in a browser?</summary>

The test suite runs on every change but has no layout, so it cannot check colour contrast. The browser check measures contrast and focus, but runs less often. Each covers what the other cannot.
</details>

<details><summary>4. An owner says the page is "confusing", but every test passes. What do you look for?</summary>

Count the signals for one state: here a status banner, a counter and three buttons (two disabled) all described the same moment. Replace them with one sentence that says what to do now and one button that does it. Then check the order of the panel against the order of the work.
</details>
