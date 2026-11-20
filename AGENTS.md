# Project instructions for AI coding agents

Before making any change, read [PROJECT_HANDBOOK.md](PROJECT_HANDBOOK.md), then the relevant ADR, runbook and issue/PR. The handbook is the durable project handoff; chat history is context, not current state.

- Confirm repository, branch, base/head SHA and worktree status before editing.
- Work only on an explicitly scoped task with acceptance criteria. Do not broaden the task or start a new product feature from a suggestion.
- Preserve human approval, evidence provenance, privacy, budget limits and the architecture decisions.
- Keep AEOS Core separate from the experimental Commercial Lead Engine unless an approved interface/task says otherwise.
- Never commit credentials, .env files, private prospect data, local databases, ignored artifacts or unreviewed bulk additions. Select files explicitly; never use `git add .`.
- Validate only the checks required by the task and report exactly what ran, against which SHA, with failures and limits.
- Update the handbook/issue/PR when status changes. Do not leave the only project state in a chat.
- Do not claim leads are verified/contactable, payments are Live, or code is production-ready without direct evidence.
