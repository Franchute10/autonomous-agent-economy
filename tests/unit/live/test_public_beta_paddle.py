"""Paddle Sandbox flow tests using simulated checkout and transaction data."""

import hashlib
import hmac
import json
from pathlib import Path
import time
from typing import cast

import pytest

from aeos.live import paddle_sandbox
from aeos.live.fix_pack import build_fix_pack, build_fix_pack_offer
from aeos.live.public_beta import (
    PublicBetaService,
    create_fix_pack_checkout_response,
    process_paddle_webhook,
    redeem_fix_pack_transaction,
)

CLIENT_TOKEN = "test_client_token_for_tests"
API_KEY = "pdl_sdbx_apikey_test_key"
WEBHOOK_SECRET = "pdl_ntfset_test_webhook_secret"
TRANSACTION_ID = "txn_" + "a" * 26
SITE_URL = "https://example.com/"


class EligibleDiagnosisService(PublicBetaService):
    def diagnose(
        self, submitted_url: object, language: object = "es"
    ) -> dict[str, object]:
        page_url = submitted_url if isinstance(submitted_url, str) else SITE_URL
        locale = (
            language if isinstance(language, str) and language in {"es", "en"} else "es"
        )
        title = {
            "es": "Títulos o descripciones repetidos",
            "en": "Repeated titles or descriptions",
        }
        text = {
            "es": "Las páginas muestran metadatos repetidos.",
            "en": "The pages show repeated metadata.",
        }
        return {
            "submitted_url": page_url,
            "language": locale,
            "platform": "WEBSITE",
            "inspection_status": "SUCCEEDED",
            "confirmed_findings": [
                {
                    "priority": 1,
                    "status": "OBSERVED",
                    "title": title,
                    "evidence": text,
                    "sources": [
                        {"url": page_url, "evidence": text},
                        {"url": page_url + "services", "evidence": text},
                    ],
                }
            ],
            "pending_verifications": [],
        }


@pytest.fixture
def sandbox_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AEOS_PADDLE_ENV", "sandbox")
    monkeypatch.setenv("AEOS_PADDLE_CLIENT_TOKEN", CLIENT_TOKEN)
    monkeypatch.setenv("AEOS_PADDLE_API_KEY", API_KEY)
    monkeypatch.setenv("AEOS_PADDLE_NOTIFICATION_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr(
        paddle_sandbox, "LOCAL_CLIENT_CONFIG", tmp_path / "missing-paddle-config.json"
    )


def _transaction(custom_data: object) -> dict[str, object]:
    return {
        "id": TRANSACTION_ID,
        "status": "completed",
        "currency_code": "USD",
        "items": [
            {
                "quantity": 1,
                "price": {
                    "id": paddle_sandbox.PADDLE_PRICE_ID,
                    "product_id": paddle_sandbox.PADDLE_PRODUCT_ID,
                    "billing_cycle": None,
                    "unit_price": {"amount": "500", "currency_code": "USD"},
                },
            }
        ],
        "details": {"totals": {"currency_code": "USD"}},
        "custom_data": custom_data,
    }


def _signed_header(raw_body: bytes) -> str:
    timestamp = str(int(time.time()))
    signed_payload = timestamp.encode("ascii") + b":" + raw_body
    digest = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    return f"ts={timestamp};h1={digest}"


def test_checkout_is_fixed_price_sandbox_and_exposes_only_public_token(
    sandbox_env: None,
) -> None:
    service = EligibleDiagnosisService()
    status, checkout = create_fix_pack_checkout_response(service, SITE_URL, "es")

    assert status == 200
    assert checkout["price_id"] == "pri_01m767jwcw14hkmd6p6jxx9xtn"
    custom_data = cast(dict[str, object], checkout["custom_data"])
    assert custom_data["aeos_product"] == "fix_pack_v1"
    assert isinstance(custom_data["aeos_order_token"], str)

    browser_config = paddle_sandbox.paddle_browser_config_script().decode("utf-8")
    assert CLIENT_TOKEN in browser_config
    assert API_KEY not in browser_config
    assert WEBHOOK_SECRET not in browser_config
    assert '"environment":"sandbox"' in browser_config


def test_confirmed_sandbox_transaction_releases_existing_fix_pack(
    sandbox_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = EligibleDiagnosisService()
    checkout = service.diagnose(SITE_URL, "es")
    result = create_fix_pack_checkout_response(service, SITE_URL, "es")[1]
    custom_data = result["custom_data"]
    transaction = _transaction(custom_data)
    monkeypatch.setattr(
        "aeos.live.public_beta.retrieve_sandbox_transaction",
        lambda transaction_id: transaction,
    )

    status, redemption = redeem_fix_pack_transaction(TRANSACTION_ID, service)

    assert status == 200
    assert redemption["filename"] == "aeos-fix-pack.md"
    markdown = cast(str, redemption["markdown"])
    assert "AEOS Fix Pack" in markdown
    assert "https://example.com/services" in markdown
    pack = build_fix_pack(checkout, language="es")
    assert pack is not None
    offer = build_fix_pack_offer(pack)
    assert offer["implementation_step_count"] == 4
    assert len(cast(list[str], offer["quality_checks"])) == 4
    assert len(cast(list[str], offer["limitations"])) == 3


@pytest.mark.parametrize(
    ("mutation", "expected_status"),
    [("wrong_price", 402), ("pending", 202)],
)
def test_invalid_or_unconfirmed_payment_does_not_release_fix_pack(
    sandbox_env: None,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    expected_status: int,
) -> None:
    service = EligibleDiagnosisService()
    checkout = create_fix_pack_checkout_response(service, SITE_URL, "es")[1]
    transaction = _transaction(checkout["custom_data"])
    if mutation == "wrong_price":
        items = cast(list[dict[str, object]], transaction["items"])
        price = cast(dict[str, object], items[0]["price"])
        price["id"] = "pri_wrong"
    else:
        transaction["status"] = "ready"
    monkeypatch.setattr(
        "aeos.live.public_beta.retrieve_sandbox_transaction",
        lambda transaction_id: transaction,
    )

    status, result = redeem_fix_pack_transaction(TRANSACTION_ID, service)

    assert status == expected_status
    assert "markdown" not in result


def test_transaction_completed_webhook_rejects_invalid_signature(
    sandbox_env: None,
) -> None:
    event = {"event_type": "transaction.completed", "data": _transaction({})}
    raw_body = json.dumps(event, separators=(",", ":")).encode("utf-8")

    status, result = process_paddle_webhook(
        raw_body, f"ts={int(time.time())};h1={'0' * 64}"
    )

    assert status == 401
    assert result == {"error": "invalid_signature"}


def test_transaction_completed_webhook_accepts_valid_sandbox_signature(
    sandbox_env: None,
) -> None:
    event = {"event_type": "transaction.completed", "data": _transaction({})}
    raw_body = json.dumps(event, separators=(",", ":")).encode("utf-8")

    status, result = process_paddle_webhook(raw_body, _signed_header(raw_body))

    assert status == 200
    assert result == {"received": True, "processed": True}


def test_free_fix_pack_diagnosis_does_not_require_paddle_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "AEOS_PADDLE_ENV",
        "AEOS_PADDLE_CLIENT_TOKEN",
        "AEOS_PADDLE_API_KEY",
        "AEOS_PADDLE_NOTIFICATION_WEBHOOK_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)

    report = EligibleDiagnosisService().diagnose(SITE_URL, "es")
    pack = build_fix_pack(report, language="es")

    assert pack is not None
    assert pack["pages"]


def test_fix_pack_does_not_sell_injected_lead_teasers() -> None:
    """Only confirmed website findings enter the paid worksheet."""
    report = EligibleDiagnosisService().diagnose(SITE_URL)
    report["leads"] = [{"source_url": "https://example.org/synthetic-lead"}]
    pack = build_fix_pack(report)
    assert pack is not None
    assert "synthetic-lead" not in json.dumps(pack)
    assert "leads" not in pack
