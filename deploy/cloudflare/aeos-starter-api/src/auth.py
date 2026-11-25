"""Fail-closed Supabase user verification; never trust local JWT claims."""
import re
from uuid import UUID

JWT_PATTERN = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
URL_PATTERN = re.compile(r"https://[a-z0-9]+\.supabase\.co")


def bearer_token(header):
    if not isinstance(header, str) or len(header) > 8192:
        return None
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1] if JWT_PATTERN.fullmatch(parts[1]) else None


async def verify_identity(header, url, key, request_user):
    """Return (HTTP status, sanitized identity/error). request_user is an async port."""
    token = bearer_token(header)
    if token is None:
        return 401, {"error": "authentication_required"}
    if not isinstance(url, str) or not URL_PATTERN.fullmatch(url):
        return 503, {"error": "authentication_unavailable"}
    if not isinstance(key, str) or not key.startswith("sb_publishable_"):
        return 503, {"error": "authentication_unavailable"}
    try:
        status, user = await request_user(url + "/auth/v1/user", key, token)
        if status in (400, 401, 403):
            return 401, {"error": "invalid_session"}
        if status != 200:
            return 503, {"error": "authentication_unavailable"}
        if not isinstance(user, dict) or user.get("is_anonymous") is not False:
            return 403, {"error": "permanent_account_required"}
        identity = str(UUID(user["id"]))
    except Exception:
        return 503, {"error": "authentication_unavailable"}
    return 200, {"user_id": identity, "authenticated": True}
