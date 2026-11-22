# licence-to-kyb

Upload a UAE trade licence and get a validated, pre-filled KYB onboarding form. A person examines only the fields that the system cannot prove correct, and a person always clicks Submit.

> **Purpose:** a complete, tested reference implementation of an agentic document workflow, and a handbook for revisiting the ideas behind it.
>
> **Status: design phase.** The architecture, the Spec Kit artifacts (constitution, spec, plan, contracts, tasks) and the decisions are written. Code follows one user story at a time, after design review.

## How it works

```
upload → check file → read pages (OCR, QR) → identify document (model) → copy fields (model)
       → check values (code) → [fix failed values: agent with read-only tools] → score confidence (code)
       → ready | needs review | reject → human review → fill KYB form → human submit → verify stored record
```

- **A workflow with one bounded agent.** Three steps use a model: route, extract and a bounded resolver. Every other step is deterministic code.
- **Strict schemas at every boundary.** Every value carries the exact text it was copied from, and code checks that text against the OCR.
- **Confidence from evidence,** not from the model's own opinion, calibrated on labelled cases.
- **The uploaded document is untrusted.** The steps that read it have no tools, or only read-only tools. Only code can write.
- **Every human correction becomes a regression test.**

## Documentation

| Document | Content |
|---|---|
| [Constitution](.specify/memory/constitution.md) | Non-negotiable project rules: workflow-first design, typed contracts, outcome-based tests, GitFlow, engineering standards |
| [Engineering practices](docs/engineering-practices.md) | Branching, CI gate, security (OWASP LLM Top 10 mapping), LLM engineering, operations |
| [Handbook](docs/handbook/) | One page per concept (architecture choice, schemas, tools and errors, agent loop, grounding, human review, security, durable execution, evals, cost, spec-driven development, engineering), each with self-check questions |
| [Architecture](docs/architecture.md) | The pipeline, one licence traced from start to finish, schemas, tool calls, trust boundaries |
| [Problem statement](docs/problem-statement.md) | Who has the problem, goal, scope, success measures |
| [Design worksheet](docs/design-worksheet.md) | Nine design decisions, each with a test |
| [Feature spec](specs/001-licence-to-kyb/spec.md) | User stories, requirements and success criteria (Spec Kit) |
| [Plan, contracts, tasks](specs/001-licence-to-kyb/) | Implementation plan, data model, contracts, test cases, tasks |
| [Decisions](docs/decisions/) | Why a workflow, why the SDK in graph nodes, why evidence-based confidence |
| [UI copy](docs/ui-copy.md) | ASD-STE100 rules and every interface string |
| [Agent design framework](docs/agent-design-framework.md) | The general method used to design this system |
| [Research](docs/research.md) | UAE licence layouts, verification services, KYB requirements, sources |

## Stack

- **Backend:** Python 3.12, LangGraph, the `anthropic` SDK, Pydantic, FastAPI, SQLite, Tesseract.
- **Frontend:** React 19, Vite, TypeScript, Astryx.

## Results

The eval report will appear here, with field accuracy, `ready` precision, review rate, cost and latency.
