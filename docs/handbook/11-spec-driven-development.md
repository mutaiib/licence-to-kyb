# 11 — Spec-driven development

## In one minute

Write down what must be true before writing the code that makes it true. This repository uses **GitHub Spec Kit**, in this order:

| Command | What it does |
|---|---|
| `constitution` | Writes the non-negotiable project rules. |
| `specify` | Writes the spec: user stories, requirements and success criteria. Technology-agnostic: what and why, not how. |
| `clarify` | Asks at most 5 targeted questions, one at a time, and records the answers in the spec. |
| `plan` | Writes the technical context, a constitution check, research decisions, the data model, contracts and a quickstart. |
| `tasks` | Writes tasks grouped by user story, with tests before implementation. |
| `analyze` | Runs a read-only consistency check across all artifacts, before any code. |
| `implement` | Builds the tasks one by one. |

## Rules

- **The spec is about what and why.** Do not name frameworks, languages or databases in it. Every requirement must be testable, and every success criterion measurable.
- **User stories are prioritised and independent.** Each one can be built, tested and shipped alone. Order work by priority, never by version labels.
- **Use the clarify questions only for real decisions.** Scope, security and user experience first. Use defaults for everything else, and record them as assumptions.
- **The constitution is a gate.** The plan must pass it before research and again after design. A violation needs a written justification.
- **Write tests from the acceptance criteria, and assert outcomes:**
  - route, reason codes, values, records and audit events
  - never function names, call order or message text

  Use value-driven case tables, and property-based tests for rules that hold over a range.
- **Get an independent review.** Run `analyze`, ideally by a reviewer who did not write the artifacts. Fix what it finds, and run it again. Here, three rounds found 4 critical and 15 high issues before any code existed.
- **One source for each fact.** Define a number once (for example, the resolver budget table) and link to it everywhere else. Restated numbers drift apart.

## In this repository

| Artifact | Location |
|---|---|
| Constitution | [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) |
| Spec, with its clarification and review notes | [`spec.md`](../../specs/001-licence-to-kyb/spec.md) |
| Plan, research, data model, contracts, quickstart | [`specs/001-licence-to-kyb/`](../../specs/001-licence-to-kyb/) |
| Value-driven test cases | [`test-cases.md`](../../specs/001-licence-to-kyb/test-cases.md) |
| Tasks, by story, tests first | [`tasks.md`](../../specs/001-licence-to-kyb/tasks.md) |
| Spec Kit skills for Claude Code | `.claude/skills/speckit-*` |

## Mistakes to avoid

- **Technology in the spec,** for example "token budget" in a requirement, instead of in the plan or a contract.
- **Tasks that test wording.** Found in review: a tool-error test that checked "meaning". It was rewritten to check structure.
- **Skipping `analyze` because the documents "look right".** Most problems were contradictions *between* files, which no single file shows.

## Self-check

<details><summary>1. Where does "resolver: at most 6 turns per round" belong, and why?</summary>

In one contract table (`resolver-tools.md`), with every other file linking to it. The spec says only that fixed limits exist. That keeps the spec technology-agnostic and stops the numbers drifting.
</details>

<details><summary>2. What makes a user story "independently testable"?</summary>

Building only that story already delivers value that can be shown and tested. For example, User Story 1 alone produces a checked draft form with evidence, before review or submission exist.
</details>

<details><summary>3. Why are spec headings like "Setup" allowed, but version labels are not?</summary>

The headings describe structure. Version labels describe scope, and scope here is expressed only by story priority. The constitution's Principle X records this rule.
</details>
