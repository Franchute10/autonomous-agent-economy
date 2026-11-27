"""Cloudflare Python Worker adapter for the AEOS Starter API."""

import asyncio
import json
from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint, fetch

from app import route
from auth import verify_identity


async def request_user(url, key, token):
    response = await asyncio.wait_for(
        fetch(
            url,
            method="GET",
            headers={"apikey": key, "Authorization": "Bearer " + token},
            redirect="error",
        ),
        timeout=8,
    )
    return response.status, await response.json() if response.status == 200 else None


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        path = urlsplit(request.url).path
        if request.method == "GET" and path == "/api/v1/me":
            status, payload = await verify_identity(
                request.headers.get("Authorization"),
                getattr(self.env, "SUPABASE_URL", None),
                getattr(self.env, "SUPABASE_PUBLISHABLE_KEY", None),
                request_user,
            )
        else:
            status, payload = route(request.method, path)
        return Response(
            json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            status=status,
            headers={
                "content-type": "application/json; charset=utf-8",
                "cache-control": "no-store",
                "x-content-type-options": "nosniff",
            },
        )
