# Autonomous Agent Economy — AEOS

## Current Status

Experimental AEOS core plus a working deterministic website-review beta.
The active beta work is on `codex/aeos-live-003c`; this branch builds on it.

- Free review: bounded public HTML inspection, evidence and inconclusive findings.
- USD 5 Fix Pack: implementation worksheet and optional prompts, Paddle **Sandbox** only.
- Automatic lead delivery and the USD 10 offer: unavailable. Lead pilots use manual
  evidence or fixtures; Overpass finds businesses, not confirmed buying intent.
- Agent definitions and invocation records exist as domain contracts. No operational
  autonomous agent runtime or model adapter drives the public beta.

See [current offer scope](docs/product/aeos-offers-v1.md),
[public beta runbook](docs/runbooks/aeos-public-beta.md), and
[review decisions and remaining release gates](docs/product/review-decisions-2026-11.md).

## Long-Term Purpose

AEOS explores how an AI-native organization can manage:

- objectives;
- resources;
- budgets;
- agents;
- workflows;
- experiments;
- governance;
- evidence;
- organizational learning.

The current repository does **not yet implement autonomous agents or economic autonomy**.

## Repository Structure

The package contains organization, governance, economics, experiments, workflow,
knowledge, agent-contract and tenancy domains, with persistence adapters and tests.
The `live` package implements website inspection, market and opportunity pilots,
and the public HTTP beta. Domain models and passing offline tests are not proof
of a running autonomous organization or of live commercial lead coverage.

The approved Working Technical Architecture v0.1 is documented in
[`docs/architecture/AEOS_Minimum_Viable_Technical_Architecture_v0.1.md`](docs/architecture/AEOS_Minimum_Viable_Technical_Architecture_v0.1.md).
Its ADR index is in [`docs/adr/README.md`](docs/adr/README.md), with dependency
rules and a fitness checklist in
[`docs/architecture/architecture-rules.md`](docs/architecture/architecture-rules.md).

## Development

Create an environment and install development dependencies:

```text
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Run the checks:

```text
pytest
ruff check .
ruff format --check .
mypy
```

Apply formatting with:

```text
ruff format .
```
