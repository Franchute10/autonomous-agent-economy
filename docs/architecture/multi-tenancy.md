# AEOS multi-tenancy foundation

## Data ownership matrix (pre-hardening audit)

This matrix records the state found at the start of LIVE-003B2, before the
security changes in this milestone.

| Data | Existing storage / owner | Tenant enforcement found | LIVE-003B2 requirement |
| --- | --- | --- | --- |
| Organizations, roles, memberships | PostgreSQL `organizations`, `roles`, `role_assignments` | Resolver checks a selected organization and membership; repository `get` is an internal unscoped primitive, while `list_for_actor` filters by actor | Keep unscoped lookup behind authorization use cases; check active membership and role for every service operation |
| Business profiles | PostgreSQL `organization_business_profiles` keyed by organization ID; source-controlled profile fixtures are synthetic; real tenant profiles belong under ignored `.aeos-private/tenants/` | New repository filters by context organization; legacy CLI reads caller-selected files; database has no RLS | Enforce resolved tenant ownership and role, add RLS, and leave legacy artifacts unchanged |
| Market research and competitors | synthetic fixtures under `examples/live/` plus local/private research inputs | Manifest reference adapter is context-scoped; pilot adapters and direct CLI paths are not | Keep immutable legacy references; scope any persisted private results by tenant; public reusable source data must be declared explicitly |
| Prospects and leads | synthetic fixtures under `examples/live/` plus local/private inputs | Pilot paths are unscoped; no tenant-aware application service | Use scoped storage and services for tenant-owned records; retain provenance and lead approval checks |
| Opportunity Inbox, contact/quote approvals | JSON through `LocalOpportunityInbox` | Caller-selected path; new tenant adapter derives a path, but only the generic local store is available | Apply tenant service authorization to reads, writes, listing, search and export; isolate duplicate checks |
| Follow-up history | JSON through `LocalOpportunityPipeline` | Caller-selected path; new tenant adapter derives a path, with no service-level CRUD boundary | Restrict access to the selected tenant and derive paths internally |
| Assessments | Computed in LIVE application services; may be included in pilot output files | Computation is shared, but there is no persisted owner or tenant-aware report path | Store private assessments under the owning organization; authorize retrieval and export |
| Reports | JSON/Markdown files written by LIVE pilots | Caller-selected output directory; no owner envelope or authorization | Persist through tenant-scoped report service; export only the selected tenant's records |
| Tenant manifests | trusted local configuration under `.aeos-private/tenants/<tenant_key>/` | Trusted local mapping verifies manifest organization ID; checked-in manifests are synthetic fixtures | Treat manifests as deployment configuration, reject path escapes, never infer ownership from filenames |
| Local persistent storage | LIVE pilot JSON stores and artifact files; application persistence also has SQL repositories | Legacy paths are unscoped; profile SQL row is tenant-keyed but has no RLS | Keep CLI stores explicitly offline/single-tenant; use the tenant adapter for service data and enforce database RLS where supported |

The current working tree keeps tenant-private data outside source control. The historical commit audit and remediation options are documented in [tenant-data-privacy.md](tenant-data-privacy.md).

## Current ownership matrix

| Data | Authoritative storage | Owner association and enforcement |
| --- | --- | --- |
| Organizations, roles, memberships | PostgreSQL organization aggregates | The resolver loads the selected organization and validates an active role assignment. A context re-reads the membership on every protected store operation. `OrganizationRepository.get` remains an internal unscoped primitive; application use cases do not return its result before authorization. |
| Business profiles | PostgreSQL `organization_business_profiles`; synthetic example JSON remains in source control; real profiles stay in local/private configuration | The table primary key and foreign key are `organization_id`; profile JSON must carry the same ID. Owner/admin role is required to create or update. PostgreSQL RLS is enabled by migration 0002. Seed profile reads use an organization-keyed manifest and return an owner envelope. |
| Market research and competitors | Read-only seed references or tenant JSON storage | Private legacy files are mapped by trusted manifests and cannot be mapped to multiple organizations. New records use an organization envelope. Reusable public material must use the explicit `public_market_sources` collection. |
| Prospects and leads | Tenant JSON storage; existing pilot files stay in place | Each record is stored under a hashed tenant directory and hashed record key, with an `organization_id` envelope. Tenant service methods scope get, create, update, delete, list, search, export, and duplicate matching. |
| Opportunity Inbox and contact/quote approvals | Tenant-aware wrapper over `LocalOpportunityInbox` | Its path is derived from the validated context and its file records the owning organization. The typed domain adapter retains provenance, duplicate, approval, and transition validation. Tenant membership is rechecked on each operation; writes require owner/admin. |
| Follow-up history | Tenant-aware wrapper over `LocalOpportunityPipeline` | Its context-derived file records the owning organization. Reads and writes recheck membership; writes require owner/admin. |
| Assessments and reports | Tenant JSON storage; existing pilot report files stay in place | Persisted records use owner envelopes. Report generation receives only records from the selected tenant; report exports list only that tenant's records. Existing CLI output paths remain offline and unscoped. |
| Tenant manifests | Trusted JSON deployment configuration under `.aeos-private/tenants/<tenant_key>/` | Manifest ID must match the configured organization key. Profile and data references must stay within the trusted root; private file paths cannot alias across organizations. The adapter reads but never rewrites a legacy artifact. |
| Local persistent storage | Context-scoped JSON adapters, `LocalTenantArtifactStorage`, plus existing PostgreSQL persistence | Tenant directories and record filenames are derived from hashes, payload owner IDs are checked recursively, symlink paths are rejected, and creates do not replace an existing record. Private artifact hashes use organization-specific roots. The OS account and storage root remain deployment-controlled. |

## Architecture review and boundary

The existing `Organization` aggregate is the tenant identity and already owns
`Role` and `RoleAssignment` objects. `RoleAssignment` records a time-bounded
actor-to-role relationship; it explicitly does not grant permission. `ActorRef`
identifies an actor but does not authenticate it. Governance persists permission
grants, approvals and decisions, but has no policy evaluator or authorization
service. This foundation reuses the existing organization and actor contracts,
and adds a small tenant authorization policy over active assignments to the
reserved tenant roles `tenant_owner`, `tenant_admin` and `tenant_member`. It does
not reinterpret general job titles or claim that persisted governance facts are
enforced.

At the start of this milestone, PostgreSQL persistence covered organization
structure and other platform aggregates but not LIVE business profiles or
commercial data. The LIVE profile, market research, prospect research,
opportunity inbox and follow-up pipeline used caller-selected local JSON paths.
Tenant-aware repositories now exist alongside those offline pilots. No trusted
authentication provider is present. No PostgreSQL test DSN was configured.

The shared vertical registry now supports Cleaning Services, HVAC,
Construction, Roofing and an extensible `OTHER` key. `HOUSE_CLEANING` remains a
legacy alias. Opportunity fit and market reporting receive the selected
business profile; tenant-specific copies of those engines are not needed.

## Tenant model

`OrganizationId` is the tenant key. An organization's business profile carries
that same ID. Trusted registration configuration may provide a stable ID;
otherwise the registration use case generates one. A `TenantPrincipal` is supplied by a trusted application boundary
after authentication; a request body must never be used to construct it. A
`TenantContextResolver` combines the principal with a selected organization,
loads the persisted organization, and verifies an active assignment to one of
the reserved tenant roles before producing `TenantContext`. Organization IDs
from requests are selectors only. Context-backed repositories recheck the
current assignment, role, and organization status on each protected operation;
a revoked or expired membership fails closed even if a caller retained an old
context.

`tenant_owner` and `tenant_admin` may register or update the organization's
business profile and write typed inbox or follow-up records. Every active
tenant role may read its organization's profile and commercial data. Generic
tenant record create/update also requires an active recognized membership;
record deletion requires owner/admin. Registration creates the existing
`Organization` aggregate, adds a `tenant_owner` role, and assigns the creator.
An inactive organization or an actor without a current recognized assignment
is denied.

Application use cases are `RegisterOrganization`, `RegisterBusinessProfile`,
`GetOrganization`, `GetBusinessProfile`, `ListOrganizationsForActor`,
`GetBusinessProfileForTenant`, `UpdateBusinessProfile` and
`TenantCommercialDataService`. Protected methods receive a principal and
organization selector, resolve the current membership, then pass only the
resulting context to the repository. Repositories derive the owner ID from that
context, not from a second request field. The commercial service covers
get/create/update/delete/list/search/export, tenant-local duplicate matching,
and report generation from that tenant's records.

## Data isolation

The additive `organization_business_profiles` table stores the existing
`BusinessProfile` contract as validated JSON with a non-null organization
foreign key and primary key. The JSON is reconstructed through the domain
constructor on every read. PostgreSQL RLS additionally filters and checks rows
using the transaction-local organization ID set by the profile repository.

The local tenant data adapter partitions records below
`org-<sha256(organization_id)>/<collection>/<sha256(record_id)>.json` and stores
the owner ID in every envelope. It checks nested owner fields, rejects
symlink-resolved paths, creates without replacing an existing record, and
atomically replaces records on update. Opportunity Inbox and follow-up history
use typed wrappers over the existing validated JSON adapters; their files also
carry the owner ID. Contact and quote approval actions remain append-only typed
inbox events, not generic approval payloads.

The manifest adapter reads files referenced by each trusted tenant manifest without copying or rewriting them. Real profiles and private research are configured under `.aeos-private/tenants/<tenant_key>/`; only synthetic fixtures remain under `examples/live/`. Private
profile/research files cannot be assigned to multiple organizations. Publicly
reusable market data must be explicitly mapped as `public_market_sources`.
Manifest paths must remain inside the trusted root. No tenant method accepts a
request-selected raw storage path.

Private artifact payloads use `LocalTenantArtifactStorage`, which validates an
active `TenantContext` on every operation and stores each organization's
content-addressed bytes beneath a hashed organization directory. The generic
`LocalFilesystemArtifactAdapter` has no tenant boundary and is reserved for
offline/platform-level use. Existing artifacts are not silently migrated;
deployments must move private legacy payloads through an explicit,
owner-reviewed migration before tenant-facing access.

Legacy unowned JSON is not assigned to the first tenant by inference and is not
visible through tenant repositories. Each local tenant manifest references its private profile and private research files in place; it does not copy them. Existing opportunity and pipeline files remain offline artifacts;
they require an explicit, reviewed ownership migration before becoming
tenant-visible. Research engines,
vertical profiles, website inspection, market discovery, evidence evaluation,
lead qualification, opportunity scoring, reporting code and agent execution
remain shared platform capabilities. Their inputs and persisted outputs are
tenant-scoped at the application/storage boundary.

## Registration and evidence

Tenant manifests contain organization metadata and references to existing
profile/research files, not duplicate research. A registration caller loads a
profile, authenticates at the application boundary, registers an organization,
then registers the profile within the resulting tenant context. The profile's
organization ID is set from that context; a conflicting ID is rejected.

Profile field status can be `REPORTED`, `OBSERVED`, `INFERRED`, `UNKNOWN` or
`NOT_PROVIDED`. `OBSERVED` requires a matching source evidence record classified
as observed with a source URL and retrieval time. Unknown and not-provided values do not turn into evidence. Existing
profile behavior remains intact when no explicit field statuses are present.
Synthetic examples use placeholders only. Real registration names, addresses, contact details, and operational facts stay in ignored local configuration.

## Security limitations

This is an application and storage foundation, not production authentication.
The repository has no identity provider or authenticated web boundary. A
`TenantPrincipal` can be constructed in Python and is not itself proof of
identity. Test actor IDs and CLI-supplied actor IDs are not production
authentication. A deployment must obtain the actor from a trusted identity
provider, validate organization membership there or through AEOS's persisted
membership repository, and construct the principal only inside that boundary.
The selected `organization_id` is never sufficient to establish membership.

`TenantDataCollection.BUSINESS_PROFILES` remains in the generic commercial-data
collection enum. Generic `TenantCommercialDataService.create` and `update` now
require owner/admin for this collection, matching the typed profile use cases.
Generic reads remain tenant-scoped; delete retains its existing owner/admin rule.

The local LIVE command-line pilots still accept file paths and do not resolve
tenant membership. They remain explicitly offline, single-tenant tools and
must not be exposed as multi-tenant service endpoints. Tenant-aware application
services must use the tenant use cases and scoped adapters. Migration 0002
defines PostgreSQL RLS for business profiles. The PostgreSQL 17 integration
suite has exercised the policy in earlier validation. No PostgreSQL DSNs were
available during LIVE-003B3, so its 11 PostgreSQL cases were skipped and no new
RLS execution is claimed. The GitHub Actions run remains pending.
RLS is defense in depth, not
authentication: `aeos.organization_id` is a transaction-local custom setting,
and any holder of the application database credentials can set it to another
tenant. An authenticated backend must establish tenant identity and select the
setting from that trusted identity. Do not expose application database
credentials or raw SQL access to tenant clients. RLS currently covers only the
`organization_business_profiles` table; the other relational tables do not
have database-level tenant isolation.

## Migration strategy

Migration `0001_initial_persistence.py` remains unchanged. Migration
`0002_org_business_profiles.py` creates the profile table, primary and
foreign keys, and PostgreSQL RLS policy. Its downgrade drops that table and
policy. SQLite migration tests are explicitly offline and verify the table,
constraints, upgrade and downgrade lifecycle; they do not simulate RLS. The
PostgreSQL integration tests require `AEOS_TEST_DATABASE_URL` for the restricted
application role and `AEOS_MIGRATION_DATABASE_URL` for the separate migration
role; they skip when the application DSN is absent. The dedicated
`.github/workflows/postgresql-security.yml` workflow provisions a disposable
PostgreSQL 17 service on `codex/**` pushes, pull requests targeting `main`, or
manual dispatch. It grants only `contents: read`, uses disposable database
credentials, and separates `aeos_migrator` from the restricted `aeos_app` role.
The earlier LIVE-003B2.1 report recorded 11 passing PostgreSQL tests; that
result was not repeated during LIVE-003B3. A successful GitHub Actions run is
still required for current CI validation.
The workflow also runs a synthetic three-tenant file-storage test; that checks
application-level scoping and is not database RLS coverage.

The repository ignores temporary pytest directories, local SQLite databases,
generated LIVE artifacts and private report output. Existing temporary files
are preserved; ignore rules keep them out of future changes without deleting
them.

Before production, add tenant ownership, scoped repositories and RLS policies
to any future relational commercial-data tables. Review whether organization,
role and membership tables also need database policies for the deployed service
role. Configure the production identity provider and database role so tenant
clients cannot set `aeos.organization_id` or run direct SQL. Confirm backup,
restore, and downgrade procedures for the profile table; the downgrade drops
profile data.

## Adding a third business

1. Create `.aeos-private/tenants/<tenant_key>/manifest.json` with a unique key/name and a
   relative reference to a private `profile.json`. Keep synthetic examples under `examples/live/tenants/`. A stable `organization_id` is optional and
   must come from trusted configuration. The manifest ID must match its
   registration key. Do not add company-specific Python modules.
2. Describe the company's vertical using a built-in key or an explicitly
   registered custom vertical key, and provide only supplied or sourced facts.
   Mark absent fields `UNKNOWN` or `NOT_PROVIDED`; attach evidence before
   marking a field `OBSERVED`.
3. Authenticate the registering actor in the deployment's trusted identity
   boundary and call `RegisterOrganization`.
4. Resolve the returned organization through `TenantContextResolver`, then call
   `RegisterBusinessProfile` with the validated profile. The use case links it
   to the resolved tenant.
5. Store new commercial data through the tenant-scoped repositories. To reuse
   legacy records, review and explicitly map their ownership before migration.
6. Run the offline test suite. In a configured deployment, also run migration
   and tenant-isolation tests against PostgreSQL with the deployed auth and
   database policies.
