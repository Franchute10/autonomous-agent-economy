# AEOS Starter API — Cloudflare Python Worker

This is a separate runtime for AEOS Starter. It does not modify the existing `lumen` Worker or the `ferreteriaconstruyeperu.com` zone. Cloudflare Workers is the intended runtime; the Python Worker entrypoint is not a Vercel Python function.

## Current scope

- Python Worker entrypoint using Cloudflare's `workers` runtime.
- `GET /health` and `GET /api/v1/capabilities` report implemented and unverified states separately.
- `GET /api/v1/me` validates a bearer token through Supabase Auth's `/auth/v1/user` endpoint and returns only the canonical user ID.
- Candidate PR #55 adds `GET /api/v1/organizations` and `POST /api/v1/organizations`. The list query is scoped to the user ID verified by Supabase Auth. Creation uses an authenticated PostgREST RPC, an idempotency UUID, and server-derived `auth.uid()`; client-supplied user and organization IDs are ignored.
- The candidate migration creates organizations and memberships with PostgreSQL RLS and an atomic owner-membership insert.
- Supabase URL and publishable key are Worker bindings. No service-role/admin key is used.

The organization API is not live-ready until the migration is applied to the dedicated `aeos-starter` project, real PostgreSQL RLS checks pass, and a staged Worker version passes runtime checks. At this checkpoint, no valid Supabase session or database request from the Worker has been verified. Do not send customer data or claim live authentication based on unit tests.

## Local checks

From this directory:

```bash
uv run pytest
```

## Deploy

Cloudflare documents Python Workers through `pywrangler`:

```bash
uv run pywrangler deploy
```

Keep the Worker on the confirmed Workers Free plan and within its free limits. Do not add paid bindings or upgrade plans.

## Next implementation gates

1. Apply the reviewed migration to the dedicated Supabase project and run synthetic two-tenant RLS and idempotency checks in a rolled-back transaction.
2. Stage a Worker version and verify missing/invalid/valid session behavior and organization reads/creation without using real customer data.
3. Build the browser signup/login and organization onboarding experience.
4. Add durable task/workflow persistence and the AEOS runtime using the canonical domain state machines.
5. Add evidence capture, human approval, and audit history. No automatic external messages.
6. Add a model adapter only within the confirmed free allocation and with per-run limits; stop if the free quota is exhausted.
