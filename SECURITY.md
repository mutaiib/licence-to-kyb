# Security policy

## Reporting a vulnerability

Report vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/mutaiib/licence-to-kyb/security/advisories/new).
Do not open a public issue. You will get an answer within 7 days.

Include the affected version or commit, the steps to reproduce, and the impact.
**Never include real documents or personal data** in a report. Use the synthetic generator
(`make data`) to build a reproducing document.

## Scope

In scope: the backend API, the graph and its tools, the frontend, the CI workflows, and the
handling of uploaded documents and personal data. The threat model and controls are in
[docs/engineering-practices.md §5](docs/engineering-practices.md#5-security), mapped to the
OWASP Top 10 for LLM Applications.

## Supported versions

Only the latest release on `main` receives security fixes, through `hotfix/x.y.z` branches.
