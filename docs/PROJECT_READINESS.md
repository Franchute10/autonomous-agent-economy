# AEOS Project Readiness and Control

**Snapshot:** 2026-11-20  
**Purpose:** operational status for project owners and reviewers. This file records verified repository state; it does not claim product, lead, or production readiness.

## Read order

1. [README](../README.md) — short project orientation.
2. [AGENTS.md](../AGENTS.md) — rules for people and coding agents.
3. [PROJECT_HANDBOOK.md](../PROJECT_HANDBOOK.md) — product intent, architecture, decision history, and durable handoff. Some dated inventory sections are historical; check this snapshot and GitHub before acting.
4. This document — current readiness, open blockers, and next work.
5. [Minimum Viable Technical Architecture](architecture/AEOS_Minimum_Viable_Technical_Architecture_v0.1.md), [ADR index](../docs/adr/README.md), then the relevant implementation runbook and pull request.

Always verify the current default branch, commit SHA, PR base/head, local working tree, and CI. A document or chat can become stale.

## Canonical repositories and access

| Repository | Visibility / default branch | Responsibility |
|---|---|---|
| [autonomous-agent-economy](https://github.com/Franchute10/autonomous-agent-economy) | Public / main | AEOS architecture, core, governance, persistence, and supervised LIVE pilots. |
| [commercial-lead-engine](https://github.com/Franchute10/commercial-lead-engine) | Public / main | Separate local-first commercial research and public-intent experiment. It is not the AEOS agent runtime. |

Both were verified public through GitHub on 2026-11-20. Public visibility gives anyone read access; it does not grant Claude, Grok, or other readers write permission. No special GitHub permission is required for them to inspect a public repository. An AI reader can still have indexing, rate-limit, or tool-specific access failures; if so, use GitHub's direct repository/file URLs or a clone.

The GitHub main branch for AEOS currently has branch protection disabled. That means direct pushes are not blocked by repository rules. Before treating the repository as professionally governed, enable protection/rules requiring pull requests and successful CI after the CI failures below are repaired. This document does not change repository settings.

Never put API keys, .env files, local databases, private prospect records, search journals, or personal data in either public repository. Keep keys in local environment variables or a secret manager. Treat public search excerpts and user-supplied content as untrusted evidence.

## Product intent and boundaries

AEOS's long-term thesis is an organization operating system for AI agents: objectives, roles, authority, workflow, budgets, evidence, approvals, persistence, audit, and learning. The governing principle is “Build an organization, not a swarm.”

The initial commercial hypothesis is a free business visibility diagnosis, followed by a small paid improvement pack and later a larger market opportunity product. The five-dollar and ten-dollar offers remain experiments, not validated demand. The promise to sell useful leads is not currently supported by repeatable verified lead yield.

Keep the projects distinct:

- AEOS Core is not a production autonomous-agent organization.
- AEOS LIVE contains supervised pilot capabilities and experimental product work.
- Commercial Lead Engine is a separate CLI-based tool for testing public search and evidence evaluation.
- Tavily search results are indexed public-web observations. They do not establish a real buyer, contactability, exact post identity, or permission to access private groups.
- No automatic outreach is in scope or implemented by the public-intent pilot.

## Current backend and execution readiness

### AEOS main

Verified at commit 6851ae3152b87ba1347e4914c259296c4f340828 on 2026-11-20.

- The checked-in README describes an early experimental architecture / pre-MVP and is stale: it says there are no business-domain entities. It conflicts with the more recent handbook and code history.
- The checked-in pyproject.toml packages the Python core and configures tests, Ruff, and mypy.
- There is no render.yaml or src/aeos/live/public_beta.py on main (GitHub returned 404 for both paths). Therefore the Public Beta server/deployment work on another local/remote line is not part of the canonical main backend.
- Do not describe public website checkout, webhooks, or lead capture as live from this branch unless a deployed URL and an end-to-end run prove it.

### AEOS open pilot pull requests

- [PR #16 — manual public request capture](https://github.com/Franchute10/autonomous-agent-economy/pull/16): open; head 771995f250755a966afb64c730abdceea6acf58b; base codex/aeos-live-003c. Captures text and URL supplied by a human; it does not fetch the post, scrape groups, prove the requester is a buyer, or contact anyone. Its reported CI was green: 880 passed, 11 skipped.
- [PR #17 — harden AEOS LIVE website and market pilots](https://github.com/Franchute10/autonomous-agent-economy/pull/17): open and stacked on PR #16's branch; head 36f79fd3f9068c538e5ed147a357063df3260483; base codex/aeos-003c-review-20261120. The local Windows report says 938 passed, 11 skipped, Ruff and source mypy passed. GitHub Actions for this exact SHA failed in the checks jobs during type checking; the full suite did not run there. The PostgreSQL tenant isolation job passed.
- The failed CI run reports type errors in test code in test_website_inspector.py, test_business_profile.py, and test_business_url_diagnosis.py. The local mypy command used mypy src/aeos, so it omitted the test files that CI checks. Fix and rerun the exact CI command before merging either stacked PR.
- PR #17 reports a large change (23 files; 4,728 insertions and 290 deletions). Review scope and tests file by file; the local followup worktree was created to preserve work, not to establish that every other worktree is clean or reconciled.

### Commercial Lead Engine

- main is a local-first Typer CLI application. It is not a hosted HTTP API, background worker, or multi-agent orchestration service.
- [PR #1 — Tavily public intent search](https://github.com/Franchute10/commercial-lead-engine/pull/1): open; head b1b0092a57ca693a9e4cf47a3ed6abfb992b3b46; base main. It uses Tavily's public index. The PR description says validation was not run there. A valid key and a bounded live search are needed to verify provider operation; never share the key in chat or commit it.
- [PR #2 — intent evidence and evaluation](https://github.com/Franchute10/commercial-lead-engine/pull/2): open; head a647263bcde2be074479321928b0cd74fc1c0252; base is PR #1's feature branch, so this is stacked, not independently mergeable to main. The PR reports 878 offline tests and 11 evaluation tests, Ruff, formatting, and source mypy. No live Tavily call was made for that report.
- The pilot's candidate label is a machine filter outcome, not a verified lead. A user-checked Facebook URL resolved to a dog adoption post while its search excerpt contained cleaning text. It was relabeled NOT_REQUEST; precision on that labelled candidate was 0%.
- Search indexing may return irrelevant, stale, misattributed, or geographically incorrect snippets. The current pilot cannot read closed Facebook/Nextdoor groups and does not automatically verify the post page. A zero-result run means “no candidate found by this provider/query/run”, not “no demand exists.”
- No live result establishes repeatable useful-lead yield, buyer identity, contactability, conversion, or willingness to pay.

## Worktree and patch control

The operator's Windows laptop has multiple historical checkouts/worktrees, downloaded patches, and branches. On 2026-11-20, the inspected workspace bundle also contained a separate older AEOS clone, a Commercial Lead Engine clone with a local commit not matching GitHub PR #2, numerous patch files, and generated review directories. These are not canonical sources. The exact current state must be refreshed from the laptop before any cleanup.

Rules:

1. Do not run git clean, reset, restore, broad git add -A, blind pull, or apply old patches to make a worktree look tidy.
2. Inventory every checkout with its repo, path, branch, HEAD, upstream, status, staged diff, unstaged diff, untracked files, ignored local data, and secrets check.
3. Classify each local change as keep, superseded, private/local-only, or discard; inspect it before moving or deleting anything.
4. Compare a patch's source SHA and file list with its destination branch before applying. Prefer a fresh worktree from current remote and explicit file selection.
5. Merge only after the PR is current, reviewable, CI green, and its base is correct. Recheck the stack after each merge.

## Ordered backlog

### P0 — Establish one trustworthy source of truth

- Fix the stale README and update historical sections of PROJECT_HANDBOOK.md; make this file the live snapshot and link it from the README.
- Produce a fresh laptop inventory for AEOS main, LIVE 003c, 003b checkpoint, review/followup, Commercial Lead Engine, and any remaining worktrees. Reconcile without deleting unclassified work.
- Fix PR #17 CI by running the same mypy scope as GitHub (source and tests), then rerun all required checks.
- Review the PR #16/#17 stack and merge only when CI and scope are acceptable.
- Reconcile Commercial Lead Engine's current local branch with remote PR #1/#2; resolve stack and validation without pushing the mismatched local clone.
- Enable PR-required branch protection/checks on AEOS main after check names are known and green. Apply equivalent rules to Commercial Lead Engine if its available CI is configured.

### P1 — Verify the backend as a deployable service

- Decide whether the public diagnostic/fix-pack beta belongs in AEOS or a separate product service; document the owner and repository boundary.
- If AEOS beta code is to ship, reconcile it from its branch/worktree into a reviewed PR based on current main. Check auth, tenant isolation, rate limits, data retention, secrets, payment sandbox/live separation, webhook signature/idempotency, delivery recovery, health checks, and rollback.
- Add an explicit CI workflow for the deployable backend and a documented local/staging smoke test. Do not label it “ready” until deployment and end-to-end smoke evidence exist.
- Document environment-variable names and secret locations, never secret values.

### P2 — Validate customer value before adding automation

- Select one business, vertical, segment, locality, and allowed source set.
- Define a small human-labelled gold set and rules for useful opportunity, wrong URL, stale signal, buyer context, locality, contactability, and disqualifiers.
- Measure precision and recall only against that labelled set, retain source URL/snippet/date and reviewer decision, and record API spend.
- Continue with an offer only after a real business confirms usefulness and a paid test validates willingness to pay. Keep outreach human-approved.

## Definition of “ready for external AI review”

Claude, Grok, or another reviewer can read both public repositories using their public GitHub URLs. They should be directed to read in this sequence: this file, AGENTS.md, PROJECT_HANDBOOK.md, README, architecture/ADR documents, then the linked open PRs. They should treat main as the only merged state, PR branches as proposals, and local-only work as unknown until documented.

This project is not yet ready to be called organized, backend-ready, production-ready, or validated for lead sales. The outstanding blockers are stale/conflicting top-level docs, unclassified laptop worktrees, stacked PRs, a failing AEOS CI type-check, no AEOS beta service on main, and no repeatable verified lead-yield evidence.

## Update protocol

At each meaningful status change, update this snapshot with the date, exact repository and SHA, PR/base/head, checks actually run, outcomes, and remaining uncertainty. Do not copy credentials or private prospect evidence into this public document.
