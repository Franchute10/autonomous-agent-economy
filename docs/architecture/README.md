# Architecture

The repository uses four provisional layers:

## Domain

Business concepts and invariants. The domain must remain independent from
databases, model providers, and external tools.

## Application

Coordinates use cases using domain objects.

## Infrastructure

Contains external technologies such as databases, LLM providers, tools, and
connectors.

## Interfaces

Contains CLI, API, and other user-facing entry points.

These boundaries are provisional and will evolve through explicit architecture
decisions.

No detailed AEOS models are defined yet.
