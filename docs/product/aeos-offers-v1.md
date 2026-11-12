# AEOS offers: scope and rollout v1

Status: product scope approved for implementation on `codex/aeos-live-003c`.
This document defines customer-facing boundaries. It does not claim that the
Market & Leads Pack is already implemented or available for purchase.

## Offer ladder

| Tier | Price | Customer outcome | Availability |
|---|---:|---|---|
| Free Review | USD 0 | A limited public website review with evidence and next steps | Available |
| AEOS Fix Pack | USD 5, one time | A practical, bounded checklist and metadata templates for confirmed website issues | Implemented in Paddle Sandbox |
| AEOS Market & Leads Pack | USD 10, one time | A sourced local-market snapshot, Porter analysis, and public lead opportunities | Scope defined; implementation pending |

All paid prices are one-time. Taxes and final amounts are calculated and shown by
Paddle Checkout. Do not advertise the USD 10 tier as purchasable until its
research workflow, checkout, delivery, and sandbox tests are complete.

## USD 5 — AEOS Fix Pack

### Included

- One business website and up to 3 pages in the free review's crawl scope.
- Only confirmed website findings are covered; inconclusive observations remain
  excluded.
- Source URLs and observed evidence for each included finding.
- For confirmed duplicate title or meta-description findings: one editable
  template per affected page, using known business/page facts and explicit
  placeholders where facts are unknown.
- One public lead opportunity teaser selected from the second- or third-ranked candidate in the full qualified list, with source URL, visible date, fit reason, and public response path. This teaser is included only when at least three candidates pass the qualification rules.
- Prioritized implementation checklist and final verification checklist.
- Downloadable Markdown report after a completed Sandbox/Live transaction, with CMS instructions and a page-specific optional prompt for an LLM/coding agent.

### Not included

- H1 or other inconclusive issues.
- Direct CMS access or edits.
- Search ranking, traffic, lead, or revenue guarantees.
- Porter analysis, the complete lead list, outreach, or ongoing monitoring.

## USD 10 — AEOS Market & Leads Pack

### Customer inputs

- Business website or a short description of the offer.
- One service/product category.
- One target city/metro and country (or one clearly bounded market).
- Optional exclusions, such as customer type, service radius, or competitors.

If the website does not establish the service or geography, ask the customer;
do not infer it silently.

### Included

The USD 10 purchase is the complete version of the USD 5 offer. It includes the Fix Pack, the highest-ranked lead, and the broader opportunity list; it is not an extra USD 10 on top of the USD 5 payment.

1. **Porter's Five Forces snapshot**
   - All five forces assessed for the stated service and geography.
   - Each force receives a Low / Medium / High pressure rating and a concise
     explanation.
   - Up to 5 named competitors or substitutes, only when supported by public
     evidence.
   - Source links and observation date for material claims.
   - An evidence/confidence note; missing evidence is labeled unknown, not
     converted into a confident rating.

2. **Public lead opportunities**
   - Up to 5 qualified public opportunities, including the highest-ranked lead and the other best-ranked candidates available. The USD 5 teaser is drawn from rank 2 or 3 when the qualified pool has at least 3 candidates.
   - Public posts or listings must explicitly indicate a current need
     matching the customer's offer and geography.
   - For each: source link, date if visible, public excerpt or short evidence
     summary, service/location match, why it qualifies, and the public response
     route if available.
   - A lead is an opportunity signal, not a verified buyer, contact, or promise
     of conversion.
   - If fewer than 5 valid opportunities are found, deliver fewer and state
     what was searched. Never pad the report with directories, competitor
     listings, or generic businesses and call them leads.

3. **Action brief**
   - Three evidence-linked next actions, ordered by practical priority.
   - Downloadable report in Markdown for the initial MVP; PDF can follow after
     the research workflow is stable.

### Research and privacy boundaries

- Use only publicly accessible pages and sources that allow access without
  joining a private group or using another person's credentials.
- Do not bypass login, access controls, robots restrictions, or platform
  protections. Do not scrape private Facebook groups or private profiles.
- Do not collect personal sensitive data, automate contact, send messages, or
  represent an opportunity as contacted.
- Show source URLs and dates so the user can check the evidence.
- Respect source terms and applicable platform rules. If a source cannot be
  accessed or its permission is unclear, exclude it and record the limitation.
- No ranking, market-share, revenue, or buyer-intent claims without direct
  evidence.

### Explicit exclusions

- No direct outreach, CRM import, lead enrichment, phone/email harvesting, or
  ongoing alerts.
- No guaranteed number of leads; the deliverable is a report with up to 5
  qualifying public opportunity signals.
- No full consulting engagement or custom strategy workshop.
- No direct changes to the customer's website or business listings.

## Current implementation gap

The public beta does not yet discover or attach real leads to its website diagnosis. The existing opportunity pilot accepts manually captured, permission-reviewed evidence; it does not run a live search connector. Do not sell or claim the lead teaser until a real, current, qualified candidate pool is available for the submitted market. Synthetic fixtures and directory listings cannot be shown as customer leads.

The Fix Pack Markdown is intended as an implementation worksheet. Customers who manage a CMS can fill the templates and edit SEO fields directly. Customers using an LLM or coding agent can paste the page-specific prompt to get a proposal; code changes still require repository access and the customer's approval. AEOS does not call an LLM automatically.

## Implementation sequence

1. **Preserve the free review and Fix Pack.** Keep the free diagnosis and the current USD 5 payment path stable while the lead capability is added.
2. **Build the market/lead intake.** Collect service, market, geography, and
   optional exclusions; do not infer missing geography. Store only the information
   needed to create and deliver the paid report.
3. **Build evidence-first research.** Add an approved public-source discovery
   method, record source/date/evidence, deduplicate opportunities, and support
   an honest zero-lead result. Do not claim Facebook or social coverage until a
   compliant source is actually integrated.
4. **Generate the report.** Produce the five-force table, lead cards, confidence
   notes, and action brief from the stored evidence.
5. **Add a separate Sandbox product/price and purchase path.** Keep the USD 5
   SKU untouched. Verify exact product, price, currency, amount, quantity, and
   order metadata server-side before delivery.
6. **Validate end to end in Sandbox.** Test intake, evidence report, payment,
   signed webhook, download, invalid/pending transactions, and zero qualifying
   leads. Deploy to the Sandbox host only after CI passes.
7. **Review before Live.** Complete Paddle business verification, check customer
   terms/privacy/refund wording, and explicitly review whether public-source
   discovery is supportable in the intended regions.

## Release acceptance criteria for USD 10

- The form requires or reliably obtains a service and one bounded market.
- Every material market claim and every lead has a source URL and observation
  date.
- Each lead meets the explicit current-need and location-match criteria.
- A search that finds no qualifying leads returns a valid report, not invented
  data or a system error.
- Private social content and authentication-gated sources are not accessed.
- Payment status is checked by the server; browser success alone cannot unlock
  the report.
- USD 5 checkout and delivery continue to work unchanged.
- Customer-facing copy says “up to 5 public opportunities” and does not promise
  leads, sales, rankings, or ROI.
- CI and the complete Sandbox purchase/delivery smoke test pass before release.

## Pricing rationale

USD 10 is a test price for a tightly bounded, mostly automated snapshot, not a
price for bespoke manual consulting. Comparable public offers advertise
one-time small-business audits near USD 9.99; this is directional context, not
proof of willingness to pay or a direct comparison to lead research. Validate
the offer with actual customer use before raising scope or promising manual
research.
