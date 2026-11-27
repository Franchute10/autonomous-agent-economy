# AEOS Starter API — Cloudflare Python Worker

This is a separate runtime for AEOS Starter. It deliberately does not modify the existing `lumen` Worker or the `ferreteriaconstruyeperu.com` zone.

## Current scope

- Python Worker entrypoint using Cloudflare's `workers` runtime.
- `GET /health` and `GET /api/v1/capabilities` expose the current implementation boundary.
- `GET /api/v1/me` validates a bearer token through Supabase Auth's `/auth/v1/user` endpoint and returns only the canonical user ID.
- The identity adapter ignores user metadata such as a client-supplied `organization_id`; authentication is not organization membership or tenant authorization.
- Supabase URL and publishable key are Worker bindings. No service-role/admin key is used.
- No database connection, organization onboarding/membership, tenant persistence, AI inference, agent execution, customer data, or external side effects yet.

The health response distinguishes an identity endpoint implemented in code from live authentication verification. Do not treat a passing unit test or a healthy Worker as proof that a real Supabase session has been accepted in the deployed environment.

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

The account's Workers billing plan must be verified before enabling any metered integrations. Keep this Worker on the Free limits; do not add paid bindings or upgrade plans.

## Next implementation gates

1. Verify the deployed `/health` and `/api/v1/me` routes with valid, invalid, expired, and missing tokens, plus missing bindings and upstream failure. Do not use customer data or claim live Auth until those checks are recorded.
2. Implement organization onboarding and membership from authenticated identity, with PostgreSQL/RLS cross-tenant tests. Never trust tenant IDs from user metadata or browser input.
3. Add durable task/workflow persistence and the AEOS runtime using the canonical domain state machines.
4. Add evidence capture, human approval, and audit history. No automatic external messages.
5. Add a model adapter only after the zero-cost constraint and provider limits are independently verified and explicitly authorized.
