"""Cloudflare Python Worker adapter for the AEOS Starter API."""

import asyncio
import json
from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint, fetch

from app import route
from auth import verify_identity
from organizations import organizations

MAX_ORGANIZATION_BODY_BYTES = 4096


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


async def request_database(url, method, key, token, payload):
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + token,
        "accept": "application/json",
    }
    options = {
        "method": method,
        "headers": headers,
        "redirect": "error",
    }
    if payload is not None:
        headers["content-type"] = "application/json"
        options["body"] = json.dumps(payload, separators=(",", ":"))
    response = await asyncio.wait_for(fetch(url, **options), timeout=8)
    if 200 <= response.status < 300:
        try:
            return response.status, await response.json()
        except Exception:
            return response.status, None
    return response.status, None


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        path = urlsplit(request.url).path
        authorization = request.headers.get("Authorization")
        supabase_url = getattr(self.env, "SUPABASE_URL", None)
        publishable_key = getattr(self.env, "SUPABASE_PUBLISHABLE_KEY", None)

        if request.method == "GET" and path == "/api/v1/me":
            status, payload = await verify_identity(
                authorization,
                supabase_url,
                publishable_key,
                request_user,
            )
        elif path == "/api/v1/organizations":
            raw_body = None
            if request.method == "POST":
                content_type = request.headers.get("Content-Type", "")
                if not content_type.lower().startswith("application/json"):
                    status, payload = 415, {"error": "json_required"}
                    return self._response(status, payload)
                content_length = request.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        if int(content_length) > MAX_ORGANIZATION_BODY_BYTES:
                            status, payload = 413, {"error": "request_too_large"}
                            return self._response(status, payload)
                    except ValueError:
                        status, payload = 400, {"error": "invalid_content_length"}
                        return self._response(status, payload)
                try:
                    raw_body = await request.text()
                except Exception:
                    status, payload = 400, {"error": "invalid_request"}
                    return self._response(status, payload)
            status, payload = await organizations(
                request.method,
                raw_body,
                authorization,
                supabase_url,
                publishable_key,
                request_user,
                request_database,
            )
        else:
            status, payload = route(request.method, path)
        return self._response(status, payload)

    @staticmethod
    def _response(status, payload):
        return Response(
            json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            status=status,
            headers={
                "content-type": "application/json; charset=utf-8",
                "cache-control": "no-store",
                "x-content-type-options": "nosniff",
            },
        )
