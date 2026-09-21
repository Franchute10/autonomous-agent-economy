# Autonomous Agent Economy — AEOS

## Current Status

Early experimental architecture / pre-MVP implementation.

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

The initial package is organized into provisional `domain`, `application`,
`infrastructure`, and `interfaces` layers. No AEOS business-domain entities
have been implemented yet.

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
