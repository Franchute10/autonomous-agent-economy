"""Tenant-scoped organization onboarding over Supabase Auth and PostgREST."""

import json
import re
from collections.abc import Awaitable, Callable
from urllib.parse import quote

from auth import URL_PATTERN, bearer_token, verify_identity

UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
MAX_BODY_BYTES = 4096
MAX_NAME_CHARS = 120
RequestDatabase = Callable[
    [str, str, str, str, dict[str, object] | None],
    Awaitable[tuple[int, object]],
]


def _error(status: int, code: str) -> tuple[int, dict[str, object]]:
    return status, {"error": code}


def _organization_name(raw_body: str | None) -> str | None:
    if not isinstance(raw_body, str) or len(raw_body.encode("utf-8")) > MAX_BODY_BYTES:
        return None
    try:
        value = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    if not isinstance(name, str):
        return None
    normalized = name.strip()
    if not 2 <= len(normalized) <= MAX_NAME_CHARS:
        return None
    if any(ord(char) < 32 for char in normalized):
        return None
    return normalized


async def organizations(
    method: str,
    raw_body: str | None,
    authorization: str | None,
    supabase_url: str | None,
    publishable_key: str | None,
    request_user: Callable[..., Awaitable[tuple[int, object]]],
    request_database: RequestDatabase,
) -> tuple[int, dict[str, object]]:
    """List or create organizations using the authenticated user's JWT and RLS."""
    if method not in {"GET", "POST"}:
        return 405, {"error": "method_not_allowed", "allowed_methods": ["GET", "POST"]}

    token = bearer_token(authorization)
    if token is None:
        return _error(401, "authentication_required")

    status, identity = await verify_identity(
        authorization, supabase_url, publishable_key, request_user
    )
    if status != 200:
        return status, identity
    if (
        not isinstance(identity, dict)
        or identity.get("authenticated") is not True
        or not isinstance(identity.get("user_id"), str)
        or UUID_PATTERN.fullmatch(identity["user_id"]) is None
        or not isinstance(supabase_url, str)
        or URL_PATTERN.fullmatch(supabase_url) is None
        or not isinstance(publishable_key, str)
    ):
        return _error(503, "service_unavailable")

    user_id = identity["user_id"]
    if method == "POST":
        name = _organization_name(raw_body)
        if name is None:
            return _error(400, "invalid_organization_name")
        endpoint = supabase_url + "/rest/v1/rpc/create_organization"
        payload: dict[str, object] | None = {"p_name": name}
    else:
        select = quote(
            "organization_id,role,organization:organizations(id,name,created_at)",
            safe="",
        )
        endpoint = (
            supabase_url
            + "/rest/v1/organization_memberships?select="
            + select
            + "&user_id=eq."
            + user_id
            + "&order=created_at.asc"
        )
        payload = None

    try:
        db_status, data = await request_database(
            endpoint, method, publishable_key, token, payload
        )
    except Exception:
        return _error(503, "database_unavailable")
    if db_status < 200 or db_status >= 300:
        return _error(503, "database_unavailable")

    if method == "POST":
        if isinstance(data, list) and len(data) == 1:
            data = data[0]
        if not isinstance(data, dict):
            return _error(503, "database_unavailable")
        organization_id = data.get("organization_id")
        result_name = data.get("name")
        role = data.get("role")
        if (
            not isinstance(organization_id, str)
            or UUID_PATTERN.fullmatch(organization_id) is None
            or result_name != name
            or role != "owner"
        ):
            return _error(503, "database_unavailable")
        return 201, {
            "organization": {
                "id": organization_id,
                "name": result_name,
                "role": role,
            }
        }

    if not isinstance(data, list):
        return _error(503, "database_unavailable")
    memberships: list[dict[str, object]] = []
    for item in data:
        if not isinstance(item, dict):
            return _error(503, "database_unavailable")
        organization = item.get("organization")
        role = item.get("role")
        if (
            not isinstance(organization, dict)
            or not isinstance(organization.get("id"), str)
            or UUID_PATTERN.fullmatch(organization["id"]) is None
            or not isinstance(organization.get("name"), str)
            or not isinstance(organization.get("created_at"), str)
            or role not in {"owner", "admin", "member", "viewer"}
        ):
            return _error(503, "database_unavailable")
        memberships.append(
            {
                "id": organization["id"],
                "name": organization["name"],
                "created_at": organization["created_at"],
                "role": role,
            }
        )
    return 200, {"organizations": memberships}
