# AEOS Starter API — Cloudflare Python Worker

This is a separate runtime for AEOS Starter. It deliberately does not modify the existing `lumen` Worker or the `ferreteriaconstruyeperu.com` zone.

## Current scope

- Python Worker entrypoint using Cloudflare's `workers` runtime.
- `GET /health` and `GET /api/v1/capabilities` only.
- 10 ms CPU and 10 subrequest caps in Wrangler configuration.
- No database, authentication, AI, secrets, customer data, or external side effects yet.

The health endpoint reports deployment health only. It is not evidence that the AEOS agent runtime is operational.

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

1. Add request-scoped Supabase Auth verification.
2. Add tenant-aware persistence and RLS tests.
3. Add a recoverable workflow runtime using AEOS domain state machines.
4. Add a free-tier Workers AI adapter with a hard daily inference budget.
5. Add evidence capture and human approval; no automatic external messages.
