"""URL query policy shared by bounded web fetches and persisted reports."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SENSITIVE_QUERY_TOKENS = frozenset(
    {
        "access",
        "auth",
        "authorization",
        "bearer",
        "code",
        "credential",
        "key",
        "jwt",
        "oauth",
        "password",
        "passwd",
        "private",
        "refresh",
        "secret",
        "session",
        "signature",
        "sig",
        "token",
    }
)
_TRACKING_KEYS = frozenset(
    {
        "dclid",
        "fbclid",
        "gclid",
        "gbraid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "msclkid",
        "_ga",
        "_gl",
        "vero_conv",
        "vero_id",
        "_hsenc",
        "_hsmi",
    }
)


def has_sensitive_query_parameter(url: str) -> bool:
    """Return true when a query key can carry authentication or session data."""

    try:
        pairs = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    except (TypeError, ValueError):
        return False
    for key, _ in pairs:
        normalized = "".join(char.lower() if char.isalnum() else "_" for char in key)
        tokens = {token for token in normalized.split("_") if token}
        if tokens & _SENSITIVE_QUERY_TOKENS:
            return True
        compact = normalized.replace("_", "")
        if compact in {
            "apikey",
            "accesstoken",
            "refreshtoken",
            "clientsecret",
            "privatekey",
            "sessionid",
            "authorizationcode",
        }:
            return True
    return False


def strip_tracking_parameters(url: str) -> str:
    """Remove known tracking keys and fragments while preserving functional parameters."""

    parts = urlsplit(url)
    if has_sensitive_query_parameter(url):
        query = ""
    else:
        retained = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            lower = key.casefold()
            if (
                lower.startswith("utm_")
                or lower in _TRACKING_KEYS
                or lower.startswith("vero_")
            ):
                continue
            retained.append((key, value))
        query = urlencode(retained, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def safe_url_for_report(url: str | None) -> str | None:
    """Return a report-safe URL without fragments, tracking, credentials, or secret values."""

    if not isinstance(url, str) or not url.strip():
        return None
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
        if parts.scheme.casefold() not in {"http", "https"} or not host:
            return "[URL omitted]"
        if parts.port is not None:
            netloc = f"{host}:{parts.port}"
        else:
            netloc = host
        if parts.netloc.casefold().startswith("www."):
            netloc = f"www.{netloc}"
        safe = strip_tracking_parameters(url.strip())
        clean = urlsplit(safe)
        return urlunsplit(
            (clean.scheme.casefold(), netloc, clean.path or "/", clean.query, "")
        )
    except (TypeError, ValueError):
        return "[URL omitted]"


def safe_text_for_report(text: str) -> str:
    """Redact sensitive query values and sanitize embedded URLs in report text."""

    import re

    key_pattern = r"(?:access[_-]?token|auth(?:orization)?|bearer|client[_-]?secret|credential|id[_-]?token|jwt|oauth[_-]?token|password|passwd|private[_-]?key|refresh[_-]?token|session(?:[_-]?id)?|signature|sig|api[_-]?key|token|code)"
    value_pattern = re.compile(rf"(?i)(\b{key_pattern}\s*=\s*)[^\s&\"'<>]+")
    sanitized = value_pattern.sub(r"\1[REDACTED]", text)
    url_pattern = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

    def replace_url(match: re.Match[str]) -> str:
        raw = match.group(0)
        suffix = ""
        while raw and raw[-1] in ".,);]":
            suffix = raw[-1] + suffix
            raw = raw[:-1]
        return (safe_url_for_report(raw) or "[URL omitted]") + suffix

    return url_pattern.sub(replace_url, sanitized)


def sanitize_report_data(value: object) -> object:
    """Recursively sanitize strings before sharing JSON report data."""

    if isinstance(value, str):
        return safe_text_for_report(value)
    if isinstance(value, dict):
        private_evidence = value.get("field") == "source_event_ref"
        sanitized: dict[object, object] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.casefold() == "source_event_ref":
                sanitized[key] = (
                    "[private reference redacted]" if item is not None else None
                )
            elif key == "value" and private_evidence and item is not None:
                sanitized[key] = "[private reference redacted]"
            else:
                sanitized[key] = sanitize_report_data(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_report_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_report_data(item) for item in value)
    return value
