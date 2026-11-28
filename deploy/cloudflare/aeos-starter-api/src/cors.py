"""Restrictive CORS policy for the AEOS Starter static preview."""

from urllib.parse import urlsplit

_ALLOWED_HOST = "aeos-starter-preview.pages.dev"


def cors_headers(origin: object) -> dict[str, str]:
    """Allow only HTTPS origins on the dedicated Pages preview project."""
    if not isinstance(origin, str) or len(origin) > 256:
        return {}
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return {}
    host = parsed.hostname
    if (
        parsed.scheme != "https"
        or not isinstance(host, str)
        or parsed.netloc != host
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or not (host == _ALLOWED_HOST or host.endswith("." + _ALLOWED_HOST))
    ):
        return {}
    return {
        "access-control-allow-origin": origin,
        "access-control-allow-methods": "GET,POST,OPTIONS",
        "access-control-allow-headers": "authorization,content-type,idempotency-key",
        "access-control-max-age": "600",
        "vary": "Origin",
    }
