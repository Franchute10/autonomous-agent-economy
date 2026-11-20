# Autonomous Agent Economy — AEOS

AEOS is an experimental project exploring how an AI-native organization can coordinate objectives, agents, workflows, budgets, evidence, approvals, and learning.

## Project status and reading order

The repository has multiple active development lines and experimental pilots. The default branch, main, is the only canonical merged state. Open pull requests and other branches are proposals until reviewed and merged. Local worktrees are not visible in GitHub unless committed and pushed.

For an accurate project handoff, read in this order:

1. [Project readiness snapshot](docs/PROJECT_READINESS.md) — current verified state, blockers, open PRs, and next work.
2. [Project handbook](PROJECT_HANDBOOK.md) — product intent, boundaries, architecture decisions, and history. Check dated status sections against the readiness snapshot.
3. [AI and contributor instructions](AGENTS.md).
4. [Minimum Viable Technical Architecture v0.1](docs/architecture/AEOS_Minimum_Viable_Technical_Architecture_v0.1.md).
5. [ADR index](docs/adr/README.md), then the runbook and PR for the task being reviewed.

## Scope

The long-term thesis is “Build an organization, not a swarm.” AEOS aims to provide organizational structure and governance for AI agents; this repository does not yet represent a production autonomous-agent organization.

AEOS Core, AEOS LIVE pilots, and the separate [Commercial Lead Engine](https://github.com/Franchute10/commercial-lead-engine) have different responsibilities. The Commercial Lead Engine is not an AEOS runtime. Search results and automated classifications are not verified leads; customer demand and paid offer viability remain unproven.

## Development

Create an environment and install development dependencies:

```text
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Run project checks:

```text
pytest
ruff check .
ruff format --check .
mypy
```

Never commit credentials, .env files, local databases, private prospect data, generated search journals, or unreviewed local artifacts. Follow [AGENTS.md](AGENTS.md) and verify the branch, commit, worktree, and CI before changing code.
