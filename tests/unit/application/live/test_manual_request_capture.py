import json
from pathlib import Path
from typing import cast

import pytest

from aeos.application.live.manual_request_capture import capture_manual_request
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.opportunity_inbox_pilot import main as opportunity_inbox_main


FIXTURES = Path(__file__).parents[2] / "live/fixtures/opportunity_inbox"


def _fixture(name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((FIXTURES / name).read_text(encoding="utf-8")),
    )


def test_fixture_captures_public_request_with_traceable_explicit_intent() -> None:
    capture = capture_manual_request(_fixture("manual_request_explicit.json"))
    intent = cast(dict[str, object], capture["intent_assessment"])
    evidence = cast(dict[str, object], capture["evidence"])

    source_url = cast(str, capture["source_url"])
    expected_source_url = (
        "https://www.facebook.com/groups/sarasota-local/posts/100000000000000/"
    )
    assert source_url == expected_source_url
    assert capture["captured_at"] == "2026-11-09T12:00:00+00:00"
    assert capture["publication_date"] == "2026-11-08"
    assert capture["city"] == "Sarasota"
    assert capture["service_requested"] == "deep cleaning"
    assert capture["access_status"] == "PUBLIC_POST_MANUALLY_VIEWED"
    assert evidence["source_url"] == capture["source_url"]
    assert "Sarasota" in str(evidence["excerpt"])
    assert intent["explicit_intent"] is True
    assert intent["classification"] == "EXPLICIT_REQUEST_IN_TEXT"
    assert "estimate" in str(intent["evidence_excerpt"]).casefold()
    assert intent["buyer_confirmed"] is False
    assert capture["contact_sent"] is False


def test_fixture_without_a_request_is_not_classified_as_a_buyer() -> None:
    capture = capture_manual_request(_fixture("manual_request_no_intent.json"))
    intent = cast(dict[str, object], capture["intent_assessment"])

    assert intent["explicit_intent"] is False
    assert intent["classification"] == "NO_EXPLICIT_REQUEST_FOUND"
    assert intent["buyer_confirmed"] is False
    assert capture["contact_sent"] is False


def test_manual_capture_does_not_accept_city_or_service_not_in_visible_text() -> None:
    payload = _fixture("manual_request_no_intent.json")
    payload["city"] = "Dallas"
    with pytest.raises(InvalidLiveContract, match="copied from"):
        capture_manual_request(payload)


def test_manual_capture_rejects_private_or_unreviewed_access_labels() -> None:
    payload = _fixture("manual_request_explicit.json")
    payload["access_status"] = "CLOSED_GROUP_UNAUTHORIZED"
    with pytest.raises(InvalidLiveContract, match="access_status"):
        capture_manual_request(payload)


def test_capture_request_cli_saves_record_without_contacting_author(
    tmp_path: Path,
) -> None:
    input_path = FIXTURES / "manual_request_no_intent.json"
    output_path = tmp_path / "capture.json"
    result = opportunity_inbox_main(
        [
            "capture-request",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
    )

    assert result == 0
    capture = cast(
        dict[str, object], json.loads(output_path.read_text(encoding="utf-8"))
    )
    intent = cast(dict[str, object], capture["intent_assessment"])
    assert intent["explicit_intent"] is False
    assert intent["buyer_confirmed"] is False
    assert capture["contact_sent"] is False
