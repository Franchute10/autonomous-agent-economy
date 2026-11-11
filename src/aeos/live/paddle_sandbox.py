"""Paddle Sandbox checkout and payment verification for the public beta."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

from aeos.live.fix_pack import build_fix_pack

PADDLE_PRODUCT_ID = "pro_01m767hpzp5ttkp3b7cscasr7f"
PADDLE_PRICE_ID = "pri_01m767jwcw14hkmd6p6jxx9xtn"
PADDLE_API_BASE_URL = "https://sandbox-api.paddle.com"
LOCAL_CLIENT_CONFIG = Path(__file__).with_name("public_beta_static") / (
    "paddle-config.local.json"
)
MAX_CHECKOUT_URL_LENGTH = 450
MAX_TRANSACTION_RESPONSE_BYTES = 100_000
SIGNATURE_TOLERANCE_SECONDS = 5
_TRANSACTION_ID = re.compile(r"txn_[a-z0-9]{26}\Z")


class PaddleConfigurationError(RuntimeError):
    """The server is not configured exclusively for Paddle Sandbox."""


def paddle_sandbox_configured() -> bool:
    """Return whether all server-side Sandbox credentials are present."""
    return (
        os.environ.get("AEOS_PADDLE_ENV", "sandbox").strip().casefold() == "sandbox"
        and _client_token().startswith("test_")
        and os.environ.get("AEOS_PADDLE_API_KEY", "").startswith("pdl_sdbx_apikey_")
        and os.environ.get("AEOS_PADDLE_NOTIFICATION_WEBHOOK_SECRET", "").startswith(
            "pdl_ntfset_"
        )
    )


def paddle_browser_config() -> dict[str, object]:
    """Return only safe client configuration; never include server credentials."""
    token = _client_token()
    return {
        "environment": "sandbox",
        "clientToken": token if token.startswith("test_") else "",
        "priceId": PADDLE_PRICE_ID,
        "enabled": paddle_sandbox_configured(),
    }


def paddle_browser_config_script() -> bytes:
    encoded = json.dumps(
        paddle_browser_config(), ensure_ascii=True, separators=(",", ":")
    )
    return f"window.AEOS_PADDLE_CONFIG = {encoded};".encode("utf-8")


def prepare_fix_pack_checkout(
    report: Mapping[str, object], *, language: str
) -> dict[str, object]:
    """Validate the free result and prepare the fixed Sandbox line item."""
    if not paddle_sandbox_configured():
        raise PaddleConfigurationError("Paddle Sandbox is not configured")
    pack = build_fix_pack(report, language=language)
    submitted_url = report.get("submitted_url")
    if pack is None or not isinstance(submitted_url, str):
        raise ValueError("No confirmed Fix Pack is available")
    if len(submitted_url) > MAX_CHECKOUT_URL_LENGTH:
        raise ValueError("The URL is too long for this checkout")

    secret = _webhook_secret()
    custom_data = {
        "aeos_product": "fix_pack_v1",
        "aeos_url": submitted_url,
        "aeos_language": language,
        "aeos_order_token": _order_token(submitted_url, language, secret),
    }
    return {"price_id": PADDLE_PRICE_ID, "custom_data": custom_data}


def verify_paddle_signature(
    raw_body: bytes,
    signature_header: str,
    secret: str,
    *,
    now: int | None = None,
) -> bool:
    """Verify Paddle's HMAC-SHA256 signature against the untouched body."""
    if not raw_body or not signature_header or not secret:
        return False

    values: dict[str, list[str]] = {}
    for part in signature_header.split(";"):
        key, separator, value = part.strip().partition("=")
        if not separator or not key or not value:
            return False
        values.setdefault(key, []).append(value)
    timestamps = values.get("ts", [])
    signatures = values.get("h1", [])
    if len(timestamps) != 1 or not signatures:
        return False

    timestamp = timestamps[0]
    if not timestamp.isdecimal() or any(
        not re.fullmatch(r"[0-9a-fA-F]{64}", value) for value in signatures
    ):
        return False
    timestamp_value = int(timestamp)
    current_time = int(time.time()) if now is None else now
    if abs(current_time - timestamp_value) > SIGNATURE_TOLERANCE_SECONDS:
        return False

    signed_payload = timestamp.encode("ascii") + b":" + raw_body
    expected = hmac.new(
        secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    return any(
        hmac.compare_digest(expected, candidate.lower()) for candidate in signatures
    )


def is_expected_completed_transaction(transaction: object) -> bool:
    """Check completion, Sandbox catalog identity, currency, amount and quantity."""
    if not isinstance(transaction, Mapping):
        return False
    if transaction.get("status") != "completed":
        return False
    if transaction.get("currency_code") != "USD":
        return False

    items = transaction.get("items")
    if not isinstance(items, list) or len(items) != 1:
        return False
    item = items[0]
    if not isinstance(item, Mapping) or item.get("quantity") != 1:
        return False
    price_value = item.get("price")
    if not isinstance(price_value, Mapping):
        return False
    if (
        price_value.get("id") != PADDLE_PRICE_ID
        or price_value.get("product_id") != PADDLE_PRODUCT_ID
        or price_value.get("billing_cycle") is not None
    ):
        return False
    unit_price = price_value.get("unit_price")
    if not isinstance(unit_price, Mapping):
        return False
    if (
        str(unit_price.get("amount")) != "500"
        or unit_price.get("currency_code") != "USD"
    ):
        return False

    details_value = transaction.get("details")
    details = details_value if isinstance(details_value, Mapping) else {}
    totals_value = details.get("totals")
    totals = totals_value if isinstance(totals_value, Mapping) else {}
    currency = totals.get("currency_code")
    return currency in (None, "USD")


def fix_pack_order_from_transaction(
    transaction: object,
) -> tuple[str, str] | None:
    """Return the signed URL and language attached to a valid Fix Pack order."""
    if not is_expected_completed_transaction(transaction):
        return None
    if not isinstance(transaction, Mapping):
        return None
    custom_data_value = transaction.get("custom_data")
    if not isinstance(custom_data_value, Mapping):
        return None
    custom_data = custom_data_value
    url = custom_data.get("aeos_url")
    language = custom_data.get("aeos_language")
    token = custom_data.get("aeos_order_token")
    if (
        custom_data.get("aeos_product") != "fix_pack_v1"
        or not isinstance(url, str)
        or len(url) > MAX_CHECKOUT_URL_LENGTH
        or not isinstance(language, str)
        or language not in {"es", "en"}
        or not isinstance(token, str)
    ):
        return None
    if not hmac.compare_digest(token, _order_token(url, language, _webhook_secret())):
        return None
    return url, language


def retrieve_sandbox_transaction(transaction_id: str) -> dict[str, object]:
    """Fetch a transaction only from Paddle's fixed Sandbox API host."""
    if not _TRANSACTION_ID.fullmatch(transaction_id):
        raise ValueError("Invalid Paddle transaction ID")
    api_key = os.environ.get("AEOS_PADDLE_API_KEY", "")
    if not api_key.startswith("pdl_sdbx_apikey_"):
        raise PaddleConfigurationError("Paddle Sandbox API key is not configured")

    request = Request(
        f"{PADDLE_API_BASE_URL}/transactions/{transaction_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        method="GET",
    )
    with urlopen(request, timeout=8) as response:
        raw_response = response.read(MAX_TRANSACTION_RESPONSE_BYTES + 1)
    if len(raw_response) > MAX_TRANSACTION_RESPONSE_BYTES:
        raise ValueError("Paddle transaction response is too large")
    payload = json.loads(raw_response)
    if not isinstance(payload, Mapping):
        raise ValueError("Unexpected Paddle transaction response")
    data_value = payload.get("data")
    if not isinstance(data_value, Mapping) or data_value.get("id") != transaction_id:
        raise ValueError("Paddle transaction response did not match the request")
    return dict(data_value)


def _client_token() -> str:
    token_value = os.environ.get("AEOS_PADDLE_CLIENT_TOKEN", "").strip()
    try:
        local_value = json.loads(LOCAL_CLIENT_CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return token_value
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(local_value, Mapping):
        return ""
    if local_value.get("environment", "sandbox") != "sandbox":
        return ""
    local_token = local_value.get("client_token")
    if isinstance(local_token, str):
        return local_token.strip()
    return token_value


def _webhook_secret() -> str:
    return os.environ.get("AEOS_PADDLE_NOTIFICATION_WEBHOOK_SECRET", "")


def _order_token(url: str, language: str, secret: str) -> str:
    message = f"aeos-fix-pack-v1\n{language}\n{url}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
