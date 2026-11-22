# Handbook: building reliable LLM systems

This handbook collects the ideas behind this repository, one topic per page. Each page has five parts:

- **In one minute:** the idea, short enough to recall before a design discussion.
- **Rules:** the decisions the idea leads to.
- **In this repository:** links to where the idea is applied, so you can see it in real code and specs.
- **Mistakes to avoid:** failure modes, several of them found in this project's own design reviews.
- **Self-check:** questions with collapsible answers, for revision.

## Topics

| # | Topic | Read it when you need to … |
|---|---|---|
| 01 | [Choosing the architecture](01-choosing-the-architecture.md) | decide between code, one call, a workflow, an agent or several agents |
| 02 | [Structured output and validation](02-structured-output-and-validation.md) | make model output safe for code to use |
| 03 | [Tool design: requests, results and errors](03-tool-design.md) | give a model tools it uses correctly, and errors that direct it |
| 04 | [The agent loop and its budgets](04-agent-loop-and-budgets.md) | write a bounded tool loop that always stops |
| 05 | [Grounding and confidence](05-grounding-and-confidence.md) | decide when a value can be trusted without a person |
| 06 | [Human in the loop](06-human-in-the-loop.md) | design approvals, overrides and hand-offs that people use well |
| 07 | [Trust boundaries and security](07-trust-boundaries-and-security.md) | stop untrusted input from causing actions, and protect personal data |
| 08 | [Durable execution and idempotency](08-durable-execution-and-idempotency.md) | survive restarts, retries and resumes without duplicate writes |
| 09 | [Evaluation](09-evaluation.md) | prove quality with numbers that hold up |
| 10 | [Observability, cost and latency](10-observability-cost-latency.md) | know what a run did, what it cost and why it was slow |
| 11 | [Spec-driven development](11-spec-driven-development.md) | go from an idea to testable requirements before code |
| 12 | [Engineering practices](12-engineering-practices.md) | run the repository like a professional project |
| 13 | [Lessons from the design reviews](13-lessons-from-design-reviews.md) | revise the real mistakes found in this design, and their fixes |
| 14 | [Model providers and local models](14-model-providers.md) | run the same code on another model, or one on your own machine |
| 15 | [UX for human review](15-ux-for-human-review.md) | build a review screen people decide on quickly and well |
| 16 | [What the checks caught](16-what-the-checks-caught.md) | revise the real bugs found while building, and which check found each |

## Revision paths

**30 minutes, before a design discussion or a technical review:**
1. Read 01, 03, 05 and 06.
2. Answer the self-check questions without opening the answers.
3. Read 13.

**2 hours, before you build a new agent system:**
1. Work through the [agent design framework](../agent-design-framework.md) for the new system.
2. Read 02, 04, 07, 08 and 09.
3. Open the matching files in this repository and compare.

**For a specific question,** search this folder for the term. Each page links to the spec, contract or code that applies it.

## How the handbook relates to the other documents

| Document | Role |
|---|---|
| [Agent design framework](../agent-design-framework.md) | the method: 13 steps (0 to 12) to design any agent system |
| [Design worksheet](../design-worksheet.md) | the method applied to this project, in nine rows |
| [Architecture](../architecture.md) | how this system works, end to end |
| [Glossary](../glossary.md) | every term, with where it lives in the code |
| [Reference](../reference.md) | API, configuration, rules, reason codes |
| [Status](../status.md) | what is complete, what is pending and why |
| [Feature spec, plan, contracts, tasks](../../specs/001-licence-to-kyb/) | the testable requirements and the build plan |
| This handbook | the reasons behind the design, for learning and revision |
