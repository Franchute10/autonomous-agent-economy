# AEOS Starter API — Cloudflare Python Worker

Cloudflare Workers is the intended runtime for AEOS Starter. The Python Worker entrypoint is not a Vercel Python function. This Worker is separate from the existing `lumen` Worker and `ferreteriaconstruyeperu.com` zone.

## Current candidate

- Python Workers SDK 1.9.7 is included in the uploaded Worker bundle.
- `GET /health` and `GET /api/v1/capabilities` distinguish implemented work from live-verified features.
- `GET /api/v1/public-config` returns only the Supabase project URL and publishable client key; it never returns a service-role key.
- `GET /api/v1/me` verifies a bearer token through Supabase Auth and returns the canonical user ID.
- `GET /api/v1/organizations` lists only memberships returned for the authenticated user.
- `POST /api/v1/organizations` creates a tenant using an authenticated PostgREST RPC, a UUID idempotency key, and server-derived `auth.uid()`. Client-supplied user or organization IDs are ignored.
- CORS accepts HTTPS origins only from the dedicated `aeos-starter-preview.pages.dev` project and its deployment subdomains. Requests omit browser credentials.
- The static preview provides signup, login, organization creation, and organization listing. Access tokens live in tab-scoped `sessionStorage`; no token is persisted in localStorage.
- Preview signup writes a user to the dedicated free `aeos-starter` Supabase project. Test only with a synthetic account and a fictitious organization name. Do not use customer data.

## Deployment status

Production remains on version 6. Version 8 is an uploaded candidate for preview testing only and has not received production traffic. Its Version URL uses the Worker's production bindings, including the dedicated `aeos-starter` Supabase project. No production secrets were changed.

The public configuration and unauthenticated gates have been observed at the Version URL. A valid user session, database request from the Worker, signup email confirmation, and end-to-end organization creation still require live verification. Do not treat unit tests or a successful version upload as live authentication proof.

## Local checks

From this directory:

```bash
uv run pytest
```

The repository CI runs lint, format, type checks, core tests, Worker adapter tests, and SDK packaging checks.

## Cost and side-effect boundaries

Keep Cloudflare Workers and Supabase on their confirmed Free tiers. Do not upgrade plans, add paid bindings, or enable paid AI services. The Worker has no model inference, agent execution, external messaging, or customer-data workflow.

## Next MVP gates

1. Verify a synthetic account signup/login and email confirmation on the dedicated preview.
2. Verify organization list/create against PostgreSQL RLS using synthetic records.
3. Build durable task and workflow persistence following the AEOS domain state machines.
4. Add evidence capture, human approvals, audit history, and a Commercial workflow. Do not automatically send external messages.
5. Add a model adapter only within confirmed free allocations with per-run limits.
