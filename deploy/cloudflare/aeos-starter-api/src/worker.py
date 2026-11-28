"""Cloudflare Python Worker adapter for the AEOS Starter API."""

import asyncio
import json
from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint, fetch

from app import public_config, route
from auth import verify_identity
from cors import cors_headers
from organizations import organizations

MAX_ORGANIZATION_BODY_BYTES = 4096
CORS_PATHS = {
    "/api/v1/public-config",
    "/api/v1/me",
    "/api/v1/organizations",
}


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
    options = {"method": method, "headers": headers, "redirect": "error"}
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
        origin = request.headers.get("Origin")
        allowed_cors = cors_headers(origin)

        if request.method == "OPTIONS":
            if path not in CORS_PATHS or not allowed_cors:
                return self._response(403, {"error": "origin_not_allowed"})
            return self._response(204, None, allowed_cors)

        supabase_url = getattr(self.env, "SUPABASE_URL", None)
        publishable_key = getattr(self.env, "SUPABASE_PUBLISHABLE_KEY", None)
        response_cors = allowed_cors if path in CORS_PATHS else {}

        if path == "/api/v1/public-config":
            status, payload = public_config(
                request.method, supabase_url, publishable_key
            )
        elif request.method == "GET" and path == "/api/v1/me":
            status, payload = await verify_identity(
                request.headers.get("Authorization"),
                supabase_url,
                publishable_key,
                request_user,
            )
        elif path == "/api/v1/organizations":
            raw_body = None
            if request.method == "POST":
                content_type = request.headers.get("Content-Type", "")
                if not content_type.lower().startswith("application/json"):
                    return self._response(
                        415, {"error": "json_required"}, response_cors
                    )
                content_length = request.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        if int(content_length) > MAX_ORGANIZATION_BODY_BYTES:
                            return self._response(
                                413, {"error": "request_too_large"}, response_cors
                            )
                    except ValueError:
                        return self._response(
                            400, {"error": "invalid_content_length"}, response_cors
                        )
                try:
                    raw_body = await request.text()
                except Exception:
                    return self._response(
                        400, {"error": "invalid_request"}, response_cors
                    )
            status, payload = await organizations(
                request.method,
                raw_body,
                request.headers.get("Idempotency-Key"),
                request.headers.get("Authorization"),
                supabase_url,
                publishable_key,
                request_user,
                request_database,
            )
        else:
            status, payload = route(request.method, path)
        return self._response(status, payload, response_cors)

    @staticmethod
    def _response(status, payload, extra_headers=None):
        headers = {
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
        }
        if payload is None:
            body = ""
        else:
            headers["content-type"] = "application/json; charset=utf-8"
            body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        if extra_headers:
            headers.update(extra_headers)
        return Response(body, status=status, headers=headers)
