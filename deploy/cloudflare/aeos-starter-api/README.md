# AEOS Starter API — Cloudflare Python Worker

This is the isolated runtime for AEOS Starter. It does not modify the existing `lumen` Worker or the `ferreteriaconstruyeperu.com` zone. Cloudflare Workers is the intended runtime; this Python Worker is not a Vercel Python function.

## Candidate scope

- Python Worker health and capability routes.
- `GET /api/v1/public-config` exposes only the public Supabase URL and publishable key needed by the static signup/login page; it never returns a service-role key.
- `GET /api/v1/me` verifies bearer sessions through Supabase Auth.
- `GET/POST /api/v1/organizations` lists and creates organizations through user-scoped PostgREST and RLS.
- Browser CORS is limited to HTTPS origins on the dedicated `aeos-starter-preview.pages.dev` project. No credentials cookies or arbitrary origins are allowed.
- The static preview uses Supabase Auth signup/password login, keeps the access token in tab-scoped sessionStorage, and supports organization creation/listing.
- Organization idempotency, tenant RLS, bounded input validation, and sanitized upstream failures.

The code is a candidate. A valid Supabase session and browser-to-Worker database request are not yet verified. Do not claim production readiness until that full flow passes. Do not use customer information.

## Local checks

From this directory:

```bash
uv run pytest
```

## Deploy boundaries

Keep the Worker on the confirmed Workers Free plan. Stage versions only; do not change traffic until health, capability, Auth, and organization checks pass. Preserve existing secret bindings with `keep_bindings`; never read or print their values. No paid bindings, model calls, or service upgrades.

## Next gates

1. Verify the staged Worker public config and unauthenticated route statuses.
2. Validate signup/login and organization API with a dedicated synthetic account, then remove it.
3. Run a two-tenant browser/API flow against PostgreSQL RLS.
4. Continue with business profile and tenant-scoped artefacts, then the durable task runtime and supervised Commercial workflow.
