# AEOS Project Readiness and Control

**Snapshot:** 2026-11-20 (refreshed after the AEOS LIVE 003C PR stack reconciliation and latest operator fetch; local `main` and other worktrees still need a fresh inventory)  
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

The latest six-checkout inventory fetched AEOS origin on 2026-11-20. GitHub `main` was `260dff3276f74a2c6d4944bc0f9fbbed363ffa74`; the local main worktree remained at `9847fce29e3ee9f83dacc02e8ee53ba8c3b5cbcf`, 3 commits ahead and 24 behind, with extensive unstaged changes. Keep it untouched while classifying its local history and files.

- The current README, AGENTS.md, and this readiness file establish a consistent entry point and reading order. The handbook remains the durable product and architecture history; date-specific statements in it should be checked against this snapshot.
- The repository packages the experimental Python core and configures tests, Ruff, and mypy.
- There is no `render.yaml` or `src/aeos/live/public_beta.py` on main (GitHub returned 404 for both paths). Public checkout, webhook handling, and lead capture are not deployed from main.
- Do not describe the product as backend-ready or production-ready without a deployed service and end-to-end evidence.

### AEOS development PR state

The 003C implementation stack has been reconciled into the development branch `codex/aeos-live-003c`; none of these changes has been merged to `main`.

- [PR #17 — harden AEOS LIVE website and market pilots](https://github.com/Franchute10/autonomous-agent-economy/pull/17): merged on 2026-11-20 into `codex/aeos-003c-review-20261120` (merge commit `9267c660cf3a750cbedbb6042114d7b35129c1c8`). Its tested head reported 938 passed, 11 skipped; Ruff check/format, source mypy, diff check, GitHub CI, and PostgreSQL Security Validation passed.
- [PR #16 — harden AEOS LIVE website, market, and request capture](https://github.com/Franchute10/autonomous-agent-economy/pull/16): merged on 2026-11-20 into `codex/aeos-live-003c` (merge commit `1376a9c29f6186a1457c1a22252535fd1cbb343f`). The combined PR adds website/report hardening, bounded URL diagnosis, manual public-request capture, market resilience and vertical coverage. CI passed on the combined stack. Manual capture records human-supplied text and URL; it does not fetch the post, scrape groups, prove a buyer, or contact anyone. Automatic Playwright rendering remains opt-in.
- [PR #31 — Overpass resilience research note](https://github.com/Franchute10/autonomous-agent-economy/pull/31): documentation-only, merged on 2026-11-20 into `codex/aeos-live-003c` (merge commit `0cc8598e2272f6da25de07826b880d37e7ab43c4`). CI passed; no live provider calls were made.
- [PR #2 — align Fix Pack scope with verified Sandbox capabilities](https://github.com/Franchute10/autonomous-agent-economy/pull/2): open, targets `codex/aeos-live-003c`, head `d2ead1d406356cc5f25b4a248ce92f2a0607b955`. GitHub reported it non-mergeable on 2026-11-20; inspect its base and conflicts before any integration. It does not make the paid beta production-ready.
- [PR #1 — test-mode $5 Fix Pack](https://github.com/Franchute10/autonomous-agent-economy/pull/1): open and draft, head `7e784dc378fada568848c56bef03ed389f52d014`. It remains non-mergeable and is not a release candidate.

The 003C branch is still a development line, not the canonical product state. Merging these PRs into it did not reconcile the historical AEOS `main` worktree or move pilot code to default `main`. Passing checks do not prove a deployed backend, verified leads, live payments, or product-market fit.

### Commercial Lead Engine

- main is a local-first Typer CLI application, not a hosted HTTP API, background worker, or multi-agent orchestration service.
- [PR #1 — public service-intent capture](https://github.com/Franchute10/commercial-lead-engine/pull/1): open, head `b1b0092a57ca693a9e4cf47a3ed6abfb992b3b46`, base `main`; GitHub reported it mergeable on 2026-11-20.
- [PR #2 — intent evidence and evaluation](https://github.com/Franchute10/commercial-lead-engine/pull/2): open, head `a647263bcde2be074479321928b0cd74fc1c0252`, stacked on PR #1's branch `feat/public-intent-capture-v1`; GitHub reported it mergeable on 2026-11-20. It adds the evaluation journal, labels/reports, and geographic qualification correction.
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

**Collected:** 2026-11-20 using the corrected PowerShell inventory script. The script fetched both repositories and listed all six registered AEOS/Commercial Lead Engine checkouts. It reported tracked/staged summaries and untracked path names only; it did not inspect ignored files, scan file contents for secrets, or compare every local blob to GitHub. Treat all dirty worktrees as preserved source until their contents are classified.

| Checkout | Branch / HEAD | State at inventory | Handling |
|---|---|---|---|
| AEOS main checkout | `main` / `9847fce29e3ee9f83dacc02e8ee53ba8c3b5cbcf` | `origin/main` was `260dff3276f74a2c6d4944bc0f9fbbed363ffa74`; local branch 3 ahead / 24 behind. 58 tracked files modified/deleted (1,362 insertions, 3,111 deletions) and 46 untracked paths; no staged diff. Three local commits remain unique by SHA in the earlier review. | Preserve. Do not pull, reset, clean, broadly stage, or push the old local history. Compare exact contents and classify private, superseded, and still-unique work first. |
| AEOS 003c followup | `codex/aeos-003c-followup-20261120` / `e4568322e4162ba0f8888c8d9f5c0ac841ac6894` | Clean and matched its upstream. | This branch’s contribution was merged through PRs #17 and #16 into the 003C development line. Keep the checkout until worktree cleanup is explicitly planned. |
| AEOS 003c review | `codex/aeos-003c-review-20261120` / `65a4b6c8d540a9c22a71f90b38e7a07f0fe4e136` | 18 commits behind upstream; 19 tracked files modified, five untracked paths, no staged diff. | Its implementation paths overlap the merged 003C PR stack. Preserve until exact local file content is checked; do not pull into the dirty worktree. |
| AEOS 003b checkpoint | `codex/aeos-live-003b-checkpoint` / `a23913cece73702c78ed6839a08b6be3e634abc0` | Clean; 1 ahead / 24 behind `origin/main`. | The commit is already an ancestor of remote `codex/aeos-live-003c`; it is not an additional unmerged feature. Do not reapply its patch. |
| AEOS LIVE 003c | `codex/aeos-live-003c` / `763d9398baf3e14e8f083886c463e50a90f59be4` | 39 commits behind upstream; 20 tracked files modified, 11 untracked paths, no staged diff. | Preserve unchanged. Its tracked paths overlap merged PR #16; implementation files overlap PRs #16/#17; the sanitized note is in PR #31. Keep the real HZ profile private. Path overlap does not establish byte-for-byte identity. |
| Commercial Lead Engine | `codex/intent-evidence-evaluation` / `a647263bcde2be074479321928b0cd74fc1c0252` | Clean and matched its upstream `origin/codex/intent-evidence-evaluation`. | Keep separate from AEOS. PRs #1/#2 remain open and stacked; review their current CI and source evidence before changing branch state. |

The current remote comparison is `main` at `260dff3276f74a2c6d4944bc0f9fbbed363ffa74` versus `codex/aeos-live-003c` at `0cc8598e2272f6da25de07826b880d37e7ab43c4`: 45 commits ahead and 14 behind, with merge base `6851ae3152b87ba1347e4914c259296c4f340828`. This is a divergent development line, not a fast-forward. The 003b checkpoint SHA is already in the 003C ancestry (0 commits unique to 003b; 54 commits exist after it on 003C). Neither fact makes the dirty local main checkout safe to push or overwrite.

The fresh inventory confirms the local main, review, and 003c worktrees remain dirty; 003c followup, 003b checkpoint, and Commercial Lead Engine are clean. The earlier uploaded bundle classified several local files, but the newly reported counts do not replace an exact content comparison of every remaining local diff. Ignored paths such as `.aeos-private/`, virtual environments, artifacts, and caches remain uninspected. No complete repository secret scan has been performed.
## Results from uploaded local-diff bundle

**Reviewed:** 2026-11-20. The operator supplied the tracked patch, untracked manifest, and archive of reviewable untracked files.

- The patch was generated with git diff origin/main -- .; it is a comparison of the entire local working tree against the fetched remote main, not a patch containing only unstaged edits. It includes the old local branch's commits, current working-tree changes, and remote documentation/code absent from that branch. Its 77-file / 23,402-insertion / 482-deletion stat must not be read as the size of new uncommitted work or applied to another worktree.
- The local main commits are not present by SHA in GitHub. Their LIVE feature set substantially overlaps the remote 003c development line. Do not cherry-pick those commits into the current remote branches or push the old main branch.
- A path-level comparison of the uploaded 003c local patch against merged PR #16/#17 found all 20 tracked paths represented. The reviewable untracked implementation files are likewise represented in those merged PRs. The distinct Overpass note was sanitized to remove pilot business names, dated with its source check, and merged through PR #31. The remaining HZ profile contains real business/person identifiers and remains private. This establishes path coverage, not byte-for-byte identity; do not reapply the old patch.
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

The six-checkout inventory is now current as of 2026-11-20. The Overpass note is sanitized and merged through PR #31; the real HZ profile remains local/private. PRs #16/#17 contain the reviewed 003C implementation path set. The old Windows worktrees have not been reset, cleaned, or overwritten. Remaining reconciliation is exact-content comparison and disposition of dirty local main, review, and 003c files; all other reported checkouts were clean.

## Ordered backlog

### P0 — Close project-control gaps

- [x] Establish a canonical entry point: README links to the readiness snapshot; AGENTS.md requires reading it before changes.
- [x] Repair the reported PR #17 type-check failures and rerun GitHub CI. The exact current head and evidence are recorded above.
- [x] Collect the initial Windows inventory and inspect/classify the uploaded main diff and untracked-file bundle.
- [x] Refresh remote refs and fast-forward the clean 003c followup worktree to `e456832`.
- [x] Refresh remote refs and review the uploaded final 003c package. Confirm the 003b commit is already in the remote 003c ancestry; avoid reapplying its patch.
- [x] Reconcile the 003c implementation path list into the development branch through PRs #16/#17; merge a sanitized Overpass note through PR #31; classify the HZ profile as local/private because it contains real identifiers.
- [x] Refresh remote refs and collect the six-checkout local inventory on 2026-11-20. Main, review, and 003c remain dirty; 003c followup, 003b, and Commercial Lead Engine were clean.
- [ ] Compare exact remaining local `main`, review, and 003c file contents against merged remote branches and classify each unique/private/superseded item. Preserve all three dirty worktrees until that review is complete.
- [x] Fetch the separate Commercial Lead Engine checkout and confirm the local intent-evaluation branch is clean against its upstream ref.
- [x] Reconcile and merge AEOS PRs #17 and #16 into the 003c development line in dependency order; merge the sanitized research note as PR #31. These merges do not target `main`.
- [ ] Review open AEOS PRs #1 and #2 against the current 003c base; PR #1 remains draft and PR #2 was reported non-mergeable. Do not merge either without refreshing its base and reviewing the diff.
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
