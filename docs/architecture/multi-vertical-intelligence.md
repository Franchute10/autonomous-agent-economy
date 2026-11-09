# Multi-vertical commercial intelligence

## Registering an organization

Create an organization through `RegisterOrganization`, then create its profile
through `RegisterBusinessProfile` using the resolved `TenantContext`. The
profile's `organization_id` is set from that context; a conflicting ID is
rejected. `tenant_owner` and `tenant_admin` may create or update a profile.
The registering actor must come from the trusted authentication boundary.

The profile keeps independent fields for industry and vertical, primary and
secondary services, products, customer segments, geography, operating capacity,
and business model (`B2B`, `B2C`, `B2B2C`, `MIXED`, or `UNKNOWN`). Each value is
owner-reported until it has its own source evidence and verification status.
Do not infer a company's services or markets from its industry label.

## Defining a vertical and services

`VerticalProfile` stores a canonical industry label, customer, partner and
supplier categories, service categories, aliases, conversion points and
research signals. The built-in registry currently includes:

| Vertical | Example service categories |
| --- | --- |
| Cleaning Services | Residential, vacation-rental turnover, deep, recurring and commercial cleaning |
| HVAC | Air-conditioning installation and repair, preventive maintenance, commercial contracts and emergency service |
| Construction | General contracting, remodeling, commercial and residential construction, specialty subcontracting |
| Roofing | Installation, repair, replacement and inspection |
| Other | Custom vertical key and profile-provided services |

`HOUSE_CLEANING` remains a compatibility alias for Cleaning Services. A
company's configured offerings remain in its profile; the registry supplies
normalization and industry categories, not proof that any company offers them.
For an unregistered custom vertical, services compare after conservative text
normalization. Adding a new taxonomy entry requires a `VerticalProfile` and
tests, but does not require a new scoring branch or customer-specific code.

Aliases are vertical-scoped. For example, an HVAC service alias is never used
to qualify a construction opportunity. Unknown or incompatible service labels
do not gain fit by matching a global cleaning-service list.

## Choosing markets and collecting evidence

Use the profile's owner-confirmed service areas or explicitly supplied
additional service areas. Keep separate research records for separate cities;
do not combine several markets into a single city record. Each market,
organization and public demand signal carries a vertical. Market reporting
rejects a market whose vertical does not match the selected profile.

Record public demand separately from organizations that may fit the customer
profile. A potential buyer or referral partner is a commercial-fit hypothesis,
not proof of a purchase. Public demand must describe an explicit request for a
service in the selected vertical and include its evidence and date before it is
considered actionable. Preserve source provenance, retrieval time, confidence,
and limitations with every finding.

## Opportunity scoring

`classify_opportunity` receives the selected `BusinessProfile`. It evaluates
configured services, owner-confirmed geography, customer segment, business
model, operating capacity and observed opportunity evidence. Its nine
explainable score components are intent (15 points), geography (15), service
fit (15), customer segment (5), recency (15), open status (15), authorized
response route (10), evidence quality (5), and capacity (5). Each component
records the opportunity evidence IDs it used and, where applicable, the
profile-field evidence IDs supporting the comparison.

The score does not establish buying intent. `HOT` requires current explicit
intent, verified open status, permission and a supported response route, plus
service and geographic fit. A fit-only prospect cannot become `HOT`. Service or
geography mismatch is `COLD`; a closed or stale request is `EXPIRED`; missing
profile, provenance, permission, or required source evidence is
`INSUFFICIENT_EVIDENCE`. `WARM` retains requests that need human review or
additional verification. Procurement scope, eligibility and workload also
require review before a response.

Duplicate detection remains independent of vertical scoring. Exact and
cross-source matches continue through the existing deduplication evidence and
review states; no contact is approved by a score alone.

## Tenant separation

`OrganizationId` is the tenant key. Tenant-facing services resolve the
authenticated principal and selected organization into `TenantContext` before
reading or writing commercial records. Scoped repositories derive ownership
from that context and check it on every operation. Duplicate search and report
generation use only the selected tenant's records. Reusable public market
sources must be explicitly declared public; private research remains
organization-owned.

Migration 0002 applies PostgreSQL RLS to organization business profiles. The
other existing relational tables do not yet have RLS. Local pilot CLIs and
caller-selected JSON files do not resolve tenant membership; keep them offline
and single-tenant. Do not expose them as tenant service endpoints.

## URL handling for website research

Website inspection rejects query keys that can carry credentials, tokens,
signatures or session data before issuing an HTTP request. It removes known
tracking parameters and fragments. Ordinary functional parameters such as a
language or pagination value may remain. If a functional URL requires a query
key that matches the sensitive-key policy, do not submit the secret-bearing
URL for inspection; provide a public, non-secret URL or a sanitized page
reference. The inspector does not accept cookies, authorization headers or
credentials.

## Production limitations

The built-in service taxonomies support profile-based qualification across
Cleaning Services, HVAC and Construction. The existing Overpass pilot has
cleaning-specific category mappings, and the website text extractor still has
cleaning-oriented service patterns. HVAC and Construction therefore need
reviewed, source-specific discovery mappings before those provider workflows
can be used. Unsupported provider mappings fail closed; no category is
fabricated.

Production also requires trusted identity integration, tenant ownership and
RLS for future relational commercial data, tenant-scoped report/export
services, operational review of custom vertical taxonomies, verified provider
permissions, and PostgreSQL CI results for the current branch. RLS is defense
in depth and does not authenticate a tenant by itself.
