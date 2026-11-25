"""Cloudflare Python Worker adapter for the AEOS Starter API."""

import json
from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint

from app import route


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        path = urlsplit(request.url).path
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
