# Manatee County procurement acquisition

This read-only MVP imports official URLs or authorized exported solicitation data
supplied by an operator. It does not crawl the site, use a browser session, log in,
register a vendor, submit a bid, or contact a buyer.

## Access findings

The County's [Bids and Proposals page](https://www.mymanatee.org/services-and-amenities/service-listing/service-details/bids-proposals)
documents active and closed solicitation lists, keyword search, and a PDF export.
The County also says that public solicitations are posted on its site and that
DemandStar provides registered vendors with additional access.

In the initial check, the linked public.mymanatee.org active-list page returned
HTTP 403 to the available reader. The linked DemandStar page returned a JavaScript
shell, and this runtime could not read either host's robots.txt. This establishes
that automated retrieval is unavailable to this run; it does not establish that
the market is empty. Automated reuse permissions and site restrictions remain
unverified, so the adapter makes no network requests. Import data only after an
operator obtains it from an authorized official source.

## Import format

Start with
examples/live/procurement/manatee_manual_import.template.json. Set
response_state to BLOCKED when the source could not be read and provide a
block_reason. A blocked response is reported as blocked, never as an empty
market.

Add each officially imported solicitation to solicitations. Use null or
"UNKNOWN" for fields that the source does not establish. Include an
official_source_url and evidence_references with the source URL and exact
field references. Keep secondary discovery links under secondary_candidates
and label each reference SECONDARY. The importer keeps all values as
REPORTED; it does not claim to have verified the original record.

The record schema accepts issuing agency, solicitation ID, title, description,
official source URL, publication and closing dates, local closing time and
timezone, location, publication status, service categories, eligibility,
operational restrictions, buying-solicitation status, and evidence references.
Unknown dates, status, scope and eligibility stay UNKNOWN in reports.

## Run the acquisition command

From the LIVE-003C worktree in Windows CMD:

~~~cmd
cd /d "C:\Users\frank\Documents\Frank\Consultoria\Cesar valle\worktrees\autonomous-agent-economy-aeos-live-003c"
set PYTHONPATH=%CD%\src
C:\Users\frank\Documents\GitHub\autonomous-agent-economy\.venv\Scripts\python.exe -m aeos.live.procurement_acquisition_cli --input examples\live\procurement\manatee_manual_import.template.json --output-dir artifacts\live\manatee-procurement --as-of 2026-11-09
~~~

The command writes local acquisition-report.json and
acquisition-report.md files. It is read-only with respect to AEOS commercial
stores. It exits with code 2 for a blocked source, 3 for malformed input, and 0
for an available source, including a valid empty response.

## Tenant profile and scoring

The authenticated pilot profile must be read through
GetBusinessProfileForTenant, via build_tenant_acquisition_report, with a
trusted TenantPrincipal supplied by the authenticated application boundary.
The CLI does not accept a real-profile path or synthesize tenant identity. This
repository has no authenticated identity provider, so the real tenant profile
cannot be loaded in this run and real tenant scoring remains blocked.

Manual import values are not promoted to OBSERVED. The report uses the existing
LIVE-003B Opportunity and classify_opportunity contracts, but these records
remain INSUFFICIENT_EVIDENCE or PENDING_PRIMARY_SOURCE until original-source
evidence is verified. Even a compatible classification requires owner review;
the workflow never contacts a buyer or submits an offer.

For a separate, clearly synthetic profile demonstration only, use the existing
fictional fixture:

~~~cmd
C:\Users\frank\Documents\GitHub\autonomous-agent-economy\.venv\Scripts\python.exe -m aeos.live.procurement_acquisition_cli --input examples\live\procurement\manatee_manual_import.template.json --output-dir artifacts\live\manatee-procurement-demo --as-of 2026-11-09 --synthetic-demo-profile examples\live\business_profiles\fictional_cleaning_company.json
~~~

The generated synthetic-demo.md is an isolated preview over fabricated data.
It is not a market result and is never actionable.

## Source candidate review

An unverified secondary candidate is shown only as PENDING_PRIMARY_SOURCE.
Its service scope, deadline, eligibility, insurance, bonding and operational fit
must not be filled from secondary listings as if they were official. The current
candidate record is kept in a local ignored run input, not in source-controlled
fixtures or default production output.
