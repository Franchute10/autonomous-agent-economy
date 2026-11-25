# Review decisions — 19 November 2026

Sources: owner-supplied Claude and Grok reviews, checked against the active code.
Their conclusions are hypotheses until supported by source code or execution.

## Decisions applied

- Publish actual capabilities in the README: domain contracts exist; autonomous
  agent execution does not drive the beta. Keep deterministic inspection claims.
- Current USD 5 delivery is the website worksheet only, using Paddle Sandbox.
  Remove the lead teaser from current inclusions. USD 10/Porter/lead bundles
  remain proposals, pending both source evidence and customer validation.
- Use `commercial-lead-engine` for a measured public-intent experiment. Its
  independent work adds full run evidence, human labels, manual-sample recall,
  opt-in publication dates, RFC date parsing and a geographic scoring regression.
  It does not automatically import search results into AEOS or sell them.

## Findings not accepted blindly

- The Stripe draft is a different feature branch. Paddle exists in this branch;
  an older PR is not evidence that Paddle is missing. No payment-provider switch.
- HTML absence is already distinguished from confirmed DOM absence in
  `business_url_diagnosis._field_presence_status`. Keep those evidence gates.
- An index date is not a human-confirmed publication date. Requesting dates can
  improve metadata coverage; it cannot guarantee useful or contactable leads.
- Source feasibility examples are synthetic planning fixtures, not current API
  permissions or proof of available integrations.

## Release gates still open

Paddle redemption currently re-runs diagnosis. If the finding disappears, it
returns `fix_no_longer_confirmed` (409) after payment. Before Live, implement
and review an immutable paid-order deliverable with expiry/retention and a
customer recovery/refund process. Do not hide this by generating invented fixes.

Verify the complete Sandbox checkout → server verification → Markdown download
flow, including site changes, process restarts, quota exhaustion and unavailable
Paddle. A receipt alone is not delivery verification. No Live deployment is
approved by this review document.

## Commercial experiment

Measure one bounded campaign before changing vocabularies again. A default pilot
may use Cleaning1126 as an existing benchmark; it does not restrict the broader
product to cleaning. Future B2B-fit campaigns need a separate source and evaluation
protocol. Avoid classifying an unrelated company as a consumer demand lead.

Use a 14-day experiment with at most 252 planned basic Tavily searches for two
9-query arms, checking the account's remaining free allowance before execution.
No scheduled paid calls are enabled by this document. Label results and a sample
of rejections; compare against manually observed public URLs from the same scope
and dates. Report retrieval coverage separately from filter retention and from
human usefulness/contactability. Stop repeated spending if three comparable runs
produce no reviewable relevant requests; inspect evidence before another change.

Five human-verified useful opportunities over 14 days and candidate precision of
at least 60% are proposed decision thresholds, not promises or measured results.
Insufficient evidence should lead to revisiting source/segment, not inventing leads.
