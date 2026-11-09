# Tenant-data privacy and local configuration

## Keep real tenant data local

Real profiles, manifests, market research, prospect records, addresses, registration identifiers, personal contact details, and private operational data belong in `.aeos-private/tenants/<tenant_key>/`. The repository ignores `.aeos-private/` in `.gitignore`. Keep only synthetic profiles, manifests, and research fixtures in `examples/live/`.

A tenant folder uses the generic contracts:

```text
.aeos-private/tenants/<tenant_key>/
  manifest.json
  profile.json
  market_research.json   # optional
  prospects.json         # optional
```

`manifest.json` contains the trusted `organization_id`, `profile_file`, and optional `shared_data_files` entries. Paths are relative to the manifest and must remain inside the configured trusted root. Build `LocalTenantFileReferenceRepository` with `from_manifest_files(root, {OrganizationId: manifest_path})`; never accept the manifest path or principal from a tenant request. The private path is local deployment configuration, not a public example or an authentication boundary.

Before replacing an existing profile, copy it into the ignored local configuration directory and verify the copy. Keep the original filename in a local archive when preserving an existing document. Do not stage `.aeos-private/`. The source-controlled fictional cleaning and HVAC manifests demonstrate the generic contract.

## Synthetic tenant examples

Only clearly fictional profiles and manifests belong in source-controlled examples. The cleaning and HVAC examples demonstrate field evidence, missing-field statuses, and manifest resolution without encoding facts about a real tenant. A real organization name, its public website, or otherwise public business facts are still tenant-specific configuration and stay local unless the owner approves publication.

Profile field evidence supports `OBSERVED`, `REPORTED`, and `INFERRED`. Required geography can be empty only when its field status is `UNKNOWN` or `NOT_PROVIDED`.

## Audit of committed data

The source-controlled `origin/main` ref reviewed for this checkpoint points to `9733f69`; its tree and ancestry did not contain the identified real-tenant records. The following information is present only in the three local commits ahead of that base:

- `f45411f` added a real tenant profile, market-research records containing business details and public contact channels, and prospect-source records with identifiers, contact routes, roles, and validation status.
- `40e1e9d` added opportunity-inbox schemas and a synthetic lead-event test fixture containing business/customer-shaped fields. No real tenant profile was identified in that commit.
- `9847fce` added a lead-source feasibility example and manual-candidate template. The historical feasibility file included the pilot identity, target markets, and source, cost, retention, and authorization notes; the current working-tree version uses synthetic values and a warning against operational use.

The business-private artifacts designated for local retention remain under ignored `.aeos-private/` storage. This checkout also retains a real-tenant profile and manifest as untracked working-tree files; the checkpoint allowlist must exclude them. They were left untouched during this review. These working-tree changes do not remove the earlier local commit objects.

## Remediation options for Git history

1. Build the checkpoint as a clean snapshot based on `origin/main`, then add only reviewed, sanitized files. This keeps the three local commits out of its ancestry and leaves existing history untouched.
2. The owner must decide whether any other refs, forks, caches, CI artifacts, or clones need review or remediation. `origin/main` was checked; other remote refs were not part of this audit.
3. If repository policy requires historical removal from any published ref, an authorized owner must approve a coordinated history rewrite and cleanup. This checkpoint does not perform that work.
4. Rotate any credential if one is later identified; this review's scans did not find credential-shaped values in the publishable working-tree files.

Do not publish the checkpoint or claim historical eradication until an authorized repository owner has reviewed the exact snapshot and approved the disposition of any other refs or copies.
