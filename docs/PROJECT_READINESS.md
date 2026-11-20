# AEOS Project Readiness and Control

**Snapshot:** 2026-11-20 (includes the post-fetch six-checkout inventory, final-package review, and current PR state)  
**Purpose:** operational status for project owners and reviewers. This file records verified repository state; it does not claim product, lead, or production readiness.

## Read order

1. [README](../README.md) — short project orientation and entry point.
2. This document — current verified readiness, open blockers, PR branches, and next work.
3. [AGENTS.md](../AGENTS.md) — rules for people and coding agents.
4. [PROJECT_HANDBOOK.md](../PROJECT_HANDBOOK.md) — product intent, architecture, decision history, and durable handoff. Some dated history is contextual; use this snapshot and GitHub for current state.
5. [Minimum Viable Technical Architecture](architecture/AEOS_Minimum_Viable_Technical_Architecture_v0.1.md), [ADR index](../docs/adr/README.md), then the relevant implementation runbook and pull request.

Always verify the current default branch, commit SHA, PR base/head, local working tree, and CI. A document or chat can become stale.

## Canonical repositories and access

| Repository | Visibility / default branch | Responsibility |
|---|---|---|
| [autonomous-agent-economy](https://github.com/Franchute10/autonomous-agent-economy) | Public / main | AEOS architecture, core, governance, persistence, and supervised LIVE pilots. |
| [commercial-lead-engine](https://github.com/Franchute10/commercial-lead-engine) | Public / main | Separate local-first commercial research and public-intent experiment. It is not the AEOS agent runtime. |

Both were verified public through GitHub on 2026-11-20. Public visibility gives anyone read access; it does not grant Claude, Grok, or other readers write permission. No special GitHub permission is required for them to inspect a public repository. An AI reader can still have indexing, rate-limit, or tool-specific access failures; if so, use GitHub's direct repository/file URLs or a clone.

As rechecked on 2026-11-20, the `main` branches of both AEOS and Commercial Lead Engine have branch protection disabled (`protected=false` in GitHub). This does not restrict public read access, but direct pushes are not blocked by repository rules. Enable pull-request and required-check rules after confirming the intended checks for each repository. This snapshot records the setting; it does not change repository settings.

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

The local worktree inventory was reported against `origin/main` at `61a9ae2362a77f3a8c8b96b98db4b88355905e10`. GitHub `main` has since advanced to `a9e1a5e0a9c9abc724357ffe01da676b17d3a8e1`, a documentation-only commit on top of `61a9ae2`. The local checkout was not refreshed after that remote advance; do not treat its ahead/behind count as current until a new fetch.

- The current README, AGENTS.md, and this readiness file establish a consistent entry point and reading order. The handbook remains the durable product and architecture history; date-specific statements in it should be checked against this snapshot.
- The repository packages the experimental Python core and configures tests, Ruff, and mypy.
- There is no `render.yaml` or `src/aeos/live/public_beta.py` on main (GitHub returned 404 for both paths). Public checkout, webhook handling, and lead capture are not deployed from main.
- Do not describe the product as backend-ready or production-ready without a deployed service and end-to-end evidence.

### AEOS open pull requests

These PRs target development branches, not main. Treat them as proposals; their green checks do not establish product readiness or safe integration to main.

- [PR #17 — harden AEOS LIVE website and market pilots](https://github.com/Franchute10/autonomous-agent-economy/pull/17): open; head `e4568322e4162ba0f8888c8d9f5c0ac841ac6894`; base `codex/aeos-003c-review-20261120`. GitHub CI and PostgreSQL Security Validation both passed on this exact head (2026-11-20). Local report: 938 passed, 11 skipped; Ruff check/format, source mypy, and diff check passed. The GitHub CI now checks the previously failing test typing as well. This corrects the prior readiness entry that said this SHA was failing.
- [PR #16 — manual public request capture](https://github.com/Franchute10/autonomous-agent-economy/pull/16): open; head `771995f250755a966afb64c730abdceea6acf58b`; base `codex/aeos-live-003c`. Latest CI and PostgreSQL Security Validation passed on this SHA. Captures text and URL supplied by a human; it does not fetch the post, scrape groups, prove the requester is a buyer, or contact anyone.
- [PR #2 — align Fix Pack scope with verified Sandbox capabilities](https://github.com/Franchute10/autonomous-agent-economy/pull/2): open; head `d2ead1d406356cc5f25b4a248ce92f2a0607b955`; base `codex/aeos-live-003c`. CI and PostgreSQL Security Validation passed on the current head. It has not been reconciled against the other open branches.
- [PR #1 — test-mode $5 Fix Pack](https://github.com/Franchute10/autonomous-agent-economy/pull/1): open and draft; head `7e784dc378fada568848c56bef03ed389f52d014`; base `codex/aeos-live-003c`. CI and PostgreSQL Security Validation passed on the current head. Draft status means it is not proposed as merge-ready.

PR #17 is stacked on PR #16's head branch, while PRs #1, #2, and #16 also target the historical `codex/aeos-live-003c` line. #1 is explicitly draft and GitHub reports it non-mergeable (`dirty`); passing CI does not resolve its base conflict. #2, #16, and #17 currently report mergeable, but none targets `main`. These branches must be compared and integrated in a deliberate sequence. Passing CI is necessary but does not replace scope review, conflict review, or reconciling the operator's remaining local worktrees.

### Commercial Lead Engine

- main is a local-first Typer CLI application, not a hosted HTTP API, background worker, or multi-agent orchestration service.
- [PR #1 — public service-intent capture](https://github.com/Franchute10/commercial-lead-engine/pull/1): open; head `b1b0092a57ca693a9e4cf47a3ed6abfb992b3b46`; base `main`. No GitHub Actions run was returned for this branch in the current check.
- [PR #2 — intent evidence and evaluation](https://github.com/Franchute10/commercial-lead-engine/pull/2): open; head `a647263bcde2be074479321928b0cd74fc1c0252`; base `feat/public-intent-capture-v1` (PR #1). This is stacked and no GitHub Actions run was returned for its current head in this check.
- Earlier local validation reports exist in the PR history, but a current repeatable live Tavily run and current branch CI have not been independently verified here. Do not treat machine classifications as verified leads.
- Tavily search results are indexed public-web observations. They do not establish a real buyer, contactability, exact post identity, or permission to access private groups. The labelled Facebook URL mismatch was relabelled `NOT_REQUEST`; precision on that labelled candidate was 0%.
- Search indexing may return irrelevant, stale, misattributed, or geographically incorrect snippets. The pilot cannot read closed Facebook/Nextdoor groups and does not automatically verify the post page. A zero-result run means no candidate was found by that provider/query/run, not that no demand exists.
- No live result establishes repeatable useful-lead yield, buyer identity, contactability, conversion, or willingness to pay. No automatic outreach is in scope or implemented.

## Worktree and patch control

The operator's Windows laptop has multiple historical checkouts/worktrees, downloaded patches, and branches. On 2026-11-20, the inspected workspace bundle also contained a separate older AEOS clone, a Commercial Lead Engine clone with a local commit not matching GitHub PR #2, numerous patch files, and generated review directories. These are not canonical sources. The exact current state must be refreshed from the laptop before any cleanup.

Rules:

1. Do not run git clean, reset, restore, broad git add -A, blind pull, or apply old patches to make a worktree look tidy.
2. Inventory every checkout with its repo, path, branch, HEAD, upstream, status, staged diff, unstaged diff, untracked files, ignored local data, and secrets check.
3. Classify each local change as keep, superseded, private/local-only, or discard; inspect it before moving or deleting anything.
4. Compare a patch's source SHA and file list with its destination branch before applying. Prefer a fresh worktree from current remote and explicit file selection.
5. Merge only after the PR is current, reviewable, CI green, and its base is correct. Recheck the stack after each merge.

## Local inventory reported by the operator

**Collected:** 2026-11-20 from Windows PowerShell output and uploaded reconciliation files. The uploaded tracked diff and untracked review bundle were inspected and classified. This latest inventory covers the AEOS worktrees registered to the AEOS checkout. It does **not** include the separate Commercial Lead Engine repository/worktree. Ignored data and secrets were not inspected. Branch counts are observations at collection time and must be refreshed before any integration or cleanup. The reported AEOS `main` checkout was 3 ahead / 21 behind the then-fetched `61a9ae2`; because GitHub `main` later advanced to `a9e1a5e`, its current divergence is unknown until the laptop fetches again.

| Checkout | Branch / HEAD | State reported | Handling |
|---|---|---|---|
| AEOS main checkout | `main` / `9847fce29e3ee9f83dacc02e8ee53ba8c3b5cbcf` | After fetching AEOS origin again, 3 commits ahead and 21 behind `origin/main` at `61a9ae2`; 58 tracked files changed (1,362 insertions, 3,111 deletions), including deletions of real pilot data; 46 untracked paths. The three local commits (`f45411f`, `40e1e9d`, `9847fce`) were not found in GitHub. | Preserve. Do not pull, reset, clean, stage broadly, or push this history. The tracked diff and untracked files were classified from the earlier bundle; ignored data and a fresh complete secret scan remain outstanding. |
| AEOS 003c followup | `codex/aeos-003c-followup-20261120` / `e4568322e4162ba0f8888c8d9f5c0ac841ac6894` | Clean and exactly matched its upstream in the latest reported PowerShell inventory. | Reconciled for this branch. Its changes remain a proposal in PR #17; they are not merged to main. |
| AEOS 003c review | `codex/aeos-003c-review-20261120` / `65a4b6c8d540a9c22a71f90b38e7a07f0fe4e136` | Latest reported state: 7 commits behind its upstream; 19 tracked files modified, five untracked files, no staged diff. | Preserve the dirty worktree. Its files substantially overlap PR #16/#17; compare exact content before any cleanup. |
| AEOS 003b checkpoint | `codex/aeos-live-003b-checkpoint` / `a23913cece73702c78ed6839a08b6be3e634abc0` | Latest reported state: one commit ahead and 20 behind `origin/main`; the commit SHA is published and is an ancestor of remote `codex/aeos-live-003c`. The checkpoint branch ref is not on origin. | Its code is already in the remote 003c development history. Do not apply `003b-a23913c.patch` again. Keep the local checkout until all worktree disposition is complete. |
| AEOS LIVE 003c | `codex/aeos-live-003c` / `763d9398baf3e14e8f083886c463e50a90f59be4` | 18 commits behind upstream; 20 tracked files modified and 11 untracked files; no staged diff reported. Its tracked changes substantially overlap the 003c review/followup work. | Preserve the dirty worktree pending fresh inventory. Keep the HZ fixture private due real business/person identifiers. Keep the Overpass note private until its client references are removed and current policy language is used. |
| Commercial Lead Engine | `codex/intent-evidence-evaluation` / `a647263bcde2be074479321928b0cd74fc1c0252` | The operator fetched this repository's origin; the local branch is clean and matches `origin/codex/intent-evidence-evaluation`. Its PR #2 is open and stacked on PR #1. | Keep separate from AEOS. Review its open PR stack independently; do not push a mismatched local clone. |

The current remote branch comparison confirms the development line is not the same as `main`: `codex/aeos-live-003c` diverges from `main` (24 commits ahead and 11 behind as of `main` `61a9ae2`). The 003b commit `a23913c` is already in that development line (33 commits ahead, 0 behind when comparing `a23913c` to `d56b48d`). It contains broad LIVE, tenancy, offer, and beta work. PR #16 proposes manual capture; PR #17 proposes website/market pilot hardening. These are overlapping implementation lines, not evidence that local data or every file is safely duplicated.

Ignored paths previously reported include `.aeos-private/`, `.venv/`, `artifacts/`, pytest temporary output, and tool caches. Their contents remain uninspected and must be treated as local data until classified. The uploaded bundle received a targeted content review, but no full current secret scan of the repositories or ignored paths was performed.

The latest PowerShell inventory confirms the AEOS main checkout remains heavily modified and diverged (3 ahead/20 behind), while 003c and 003c-review contain overlapping residual diffs; 003c-followup is clean. The 003b commit is already in remote 003c, so its exported patch is redundant. The final ZIP review classified its HZ profile as private and its Overpass note as an unpublished research draft pending sanitization. Commercial Lead Engine is clean against its cached upstream ref but still needs an independent fetch. No cleanup or history rewrite has been performed. Do not run `git pull`, `reset`, `restore`, `clean`, broad staging, or history rewrites on the dirty worktrees until their exact diffs and disposition are recorded.

## Results from uploaded local-diff bundle

**Reviewed:** 2026-11-20. The operator supplied the tracked patch, untracked manifest, and archive of reviewable untracked files.

- The patch was generated with git diff origin/main -- .; it is a comparison of the entire local working tree against the fetched remote main, not a patch containing only unstaged edits. It includes the old local branch's commits, current working-tree changes, and remote documentation/code absent from that branch. Its 77-file / 23,402-insertion / 482-deletion stat must not be read as the size of new uncommitted work or applied to another worktree.
- The local main commits are not present by SHA in GitHub. Their LIVE feature set substantially overlaps the remote 003c development line. Do not cherry-pick those commits into the current remote branches or push the old main branch.
- A path-level comparison of the uploaded 003c local patch against PR #16/#17 found all 20 tracked paths represented in those PRs. Nine of ten files in the 003c new-files ZIP are also represented; the unshared file is the Overpass research note, which remains private pending sanitization. This establishes path coverage, not byte-for-byte identity. Do not reapply the old patch.
- Several untracked tenancy files match the remote 003c followup branch exactly. Other local copies are older than the branch: remote storage requires tenant-manager attestation for evidence-bearing opportunity records, parses profile documents through the current profile contract, and marks synthetic records explicitly. Use the remote version as the candidate source after reviewing the PR stack; do not overwrite it with the local copy.
- The local playwright_dom_capture.py module and its tests are not present on the remote followup branch. The module checks public DNS results before browser navigation but does not pin the browser's actual network connection to those results. Keep it out of integration until network-level egress controls and SSRF regression coverage are designed. The existing remote pilot keeps automatic browser rendering disabled.
- The untracked business profile and tenant manifest describe a real organization and are marked non-fictional. Keep them outside the public repository in ignored private tenant configuration unless publication is separately approved.
- The Paddle Sandbox example is explicitly non-fulfilling: its README says a verified server-side webhook and delivery path are still needed. Keep it labelled as test-only; it does not establish a working paid product.
- The linkedin-leadgen/ scripts, review, and assets are Lumen marketing materials, outside AEOS's repository boundary. Keep them out of AEOS; relocate them to the appropriate Lumen workspace/repository after checking that repository's current state.
- The uploaded synthetic cleaning fixtures are older than the remote fixtures. The remote examples add explicit synthetic-record markers and remove contact-like placeholder URLs; prefer the remote versions.
- A targeted pattern scan of the uploaded text found no provider credential-shaped tokens. It is not a full repository secret scan. It did identify fixed disposable PostgreSQL test passwords in the untracked CI workflow; these are test-only values, not production credentials. A Tavily credential was previously pasted into the conversation and still needs rotation.

The upload review classifies the local material but does not authorize deleting worktrees, rewriting local history, or publishing the real-tenant and Lumen files. The full local history still needs an owner-approved disposition for the real-tenant records in the three local main commits. No file cleanup or history rewrite has been performed.

## Final reconciliation package (2026-11-20)

The operator attached the ZIP and its three key files. The patch and both local 003c files were reviewed.

- `003b-a23913c.patch`: this is a full commit patch for `a23913cece73702c78ed6839a08b6be3e634abc0`, not an uncommitted diff. GitHub contains the commit, and comparison confirms it is an ancestor of remote `codex/aeos-live-003c` at `d56b48d53b1354d53c3e640247d2208fe45753fe` (33 commits ahead, 0 behind). Its code is in the development branch, not main. Do not apply the patch or duplicate its changes.
- `tests/unit/live/fixtures/profiles/hz-air-conditioning-services.json`: reviewed. It contains identifying information for a real HVAC business, including a registered address, a named registered agent, a registration identifier, and business social URLs. Do not add this fixture to this public repository. Keep the original local/private; if a public test fixture is needed, replace all identifying values and evidence with clearly synthetic data.
- `docs/research/AEOS-LIVE-003C-overpass-resilience.md`: reviewed. Its 504 observations are dated 2026-11-09; the note says the validation made no live market calls, and its tests simulate provider responses. The note names real pilot businesses, so do not publish this exact copy. Keep a sanitized, dated research record if needed. The current [OpenStreetMap Wiki instance guidance](https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances) still lists the VK Maps endpoint and says it may be used in projects, but also warns public instances can be overloaded and unreliable and advises commercial use to use self-hosted or paid servers. An unannounced request limit is not an availability commitment or commercial-service endorsement. Keep free public Overpass usage to low-volume experiments subject to the operator's terms; do not rely on it for production.

The final ZIP is reviewed. Remaining local reconciliation is limited to the dirty main/review/003c Windows worktrees and the separate Commercial Lead Engine checkout; do not clean or rewrite them until their current diffs and private data are inventoried.

## Ordered backlog

### P0 — Close project-control gaps

- [x] Establish a canonical entry point: README links to the readiness snapshot; AGENTS.md requires reading it before changes.
- [x] Repair the reported PR #17 type-check failures and rerun GitHub CI. The exact current head and evidence are recorded above.
- [x] Collect the initial Windows inventory and inspect/classify the uploaded main diff and untracked-file bundle.
- [x] Refresh remote refs and fast-forward the clean 003c followup worktree to `e456832`.
- [x] Refresh AEOS remote refs and collect the latest six-checkout PowerShell inventory; 003c-followup is clean, while main/review/003c remain dirty. Confirm the 003b commit is already published in the remote 003c ancestry.
- [ ] Finish the remaining local main/review/003c diff comparison and inspect the HZ profile fixture; document keep/quarantine decisions before integration or cleanup. The 003b commit ancestry and patch redundancy are now verified.
- [x] Fetch the separate Commercial Lead Engine checkout and confirm the local intent-evaluation branch is clean against its upstream ref.
- [ ] Review and reconcile the AEOS PR stack. Confirm the correct ancestry, inspect combined diff scope, and merge in dependency order only after local worktree reconciliation.
- [ ] Reconcile the Commercial Lead Engine local checkout with PR #1/#2; do not push the mismatched local clone.
- [ ] Configure PR-required branch rules for both public repositories after the required check names are verified. The AEOS main branch was last observed without protection; this GitHub connection did not provide a successful settings update.
- [ ] Run a repository secret scan and rotate any credential previously pasted into conversation or stored in local history. Never copy credential values into this public repository.

### P1 — Verify a deployable backend

- [ ] Decide whether the public diagnostic/Fix Pack beta belongs in AEOS or a separate product service; document its owner and repository boundary.
- [ ] If beta code is to ship, reconcile it into a reviewed PR based on current main. Check authentication, tenant isolation, rate limits, retention, secrets, payment sandbox/live separation, webhook signatures/idempotency, delivery recovery, health checks, and rollback.
- [ ] Add explicit CI for the deployable backend and a documented local/staging smoke test. Do not label it ready until deployment and end-to-end smoke evidence exist.
- [ ] Document environment-variable names and secret locations, never secret values.

### P2 — Validate customer value

- [ ] Select one business, vertical, segment, locality, and allowed source set.
- [ ] Define a small human-labelled gold set and rules for useful opportunity, wrong URL, stale signal, buyer context, locality, contactability, and disqualifiers.
- [ ] Measure precision and recall only against that labelled set, retain source URL/snippet/date and reviewer decision, and record API spend.
- [ ] Continue an offer only after a real business confirms usefulness and a paid test validates willingness to pay. Keep outreach human-approved.

## Definition of “ready for external AI review”

Both canonical repositories are public and readable without special GitHub permission:

- https://github.com/Franchute10/autonomous-agent-economy
- https://github.com/Franchute10/commercial-lead-engine

The repository-level reading sequence is ready: README → PROJECT_READINESS → AGENTS.md → PROJECT_HANDBOOK → architecture/ADR → task-specific runbook and open PRs. For now, external reviewers should be asked to audit the project status, not to implement or merge changes. They should treat main as the merged source of truth, PR branches as proposals, and local-only work as unknown.

This is an organized handoff baseline, not a fully reconciled project. Remaining blockers are stale status/content checks for the other Windows worktrees, stacked PR dependencies and combined scope review, branch protection, a full current secret scan and credential rotation, absence of a deployable beta service on AEOS main, and lack of repeatable verified lead-yield evidence. Do not create the separate-model master prompt until those repository/worktree-control checks are completed and this snapshot is refreshed again.

## Update protocol

At each meaningful status change, update this snapshot with the date, exact repository and SHA, PR/base/head, checks actually run, outcomes, and remaining uncertainty. Do not copy credentials or private prospect evidence into this public document.
