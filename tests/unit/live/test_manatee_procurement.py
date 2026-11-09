from datetime import date, datetime, timezone

from aeos.live.adapters.manatee_procurement import (
    AcquisitionState,
    MANATEE_BIDS_URL,
    parse_manual_import,
    deadline_disposition,
    opportunity_for_import,
)
from aeos.live.domain.evidence import EvidenceKind
from aeos.live.domain.opportunity_inbox import (
    LeadClassification,
    classify_opportunity,
)


_NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def _official_record(
    *,
    solicitation_id: str = "SYN-001",
    title: str = "Synthetic procurement record",
    url: str = MANATEE_BIDS_URL,
) -> dict[str, object]:
    return {
        "issuing_agency": "Manatee County",
        "solicitation_id": solicitation_id,
        "title": title,
        "description": None,
        "official_source_url": url,
        "publication_date": None,
        "closing_date": None,
        "closing_time_local": None,
        "closing_timezone": None,
        "location": None,
        "city": None,
        "state": None,
        "publication_status": None,
        "service_categories": None,
        "eligibility_requirements": None,
        "operational_restrictions": None,
        "buying_solicitation": None,
        "evidence_references": [
            {
                "reference_id": "fixture-primary",
                "kind": "OFFICIAL_PRIMARY",
                "url": url,
                "label": "Synthetic test reference; not a real solicitation",
                "fields": ["solicitation_id", "title"],
                "excerpt": "Synthetic test data only.",
            }
        ],
    }


def _document(
    *,
    response_state: str = "AVAILABLE",
    solicitations: list[dict[str, object]] | None = None,
    block_reason: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "source": {
            "name": "Manatee County Bids and Proposals",
            "starting_url": MANATEE_BIDS_URL,
            "access_mode": "MANUAL_IMPORT",
            "response_state": response_state,
            "block_reason": block_reason,
        },
        "solicitations": solicitations or [],
        "secondary_candidates": [],
    }


def test_manual_import_keeps_claims_reported_and_reuses_existing_classifier() -> None:
    batch = parse_manual_import(
        _document(solicitations=[_official_record()]), retrieved_at=_NOW
    )

    assert batch.state is AcquisitionState.SUCCESS
    record = batch.solicitations[0]
    assert record.retrieved_at == _NOW
    opportunity = opportunity_for_import(record)
    assert opportunity is not None
    assert opportunity.source_provenance.value == "UNKNOWN"
    assert opportunity.title == "Synthetic procurement record"
    assert opportunity.publication_date is None
    assert opportunity.official_deadline is None
    assert opportunity.service_requested == "UNKNOWN"
    assert all(item.kind is EvidenceKind.REPORTED for item in opportunity.evidence)

    assessment = classify_opportunity(opportunity, as_of=date(2026, 11, 9))
    assert assessment.classification is LeadClassification.INSUFFICIENT_EVIDENCE
    assert "provenance is UNKNOWN" in assessment.classification_reasons_es[0]


def test_available_empty_source_is_distinct_from_blocked_source() -> None:
    empty = parse_manual_import(_document(), retrieved_at=_NOW)
    blocked = parse_manual_import(
        _document(response_state="BLOCKED", block_reason="HTTP 403"),
        retrieved_at=_NOW,
    )

    assert empty.state is AcquisitionState.EMPTY
    assert blocked.state is AcquisitionState.BLOCKED
    assert blocked.block_reason == "HTTP 403"
    assert blocked.solicitations == ()


def test_duplicate_identity_uses_agency_and_solicitation_id_first() -> None:
    first = _official_record(title="Synthetic title A")
    second = _official_record(
        title="Synthetic title B",
        url="https://public.mymanatee.org/rfp_post/controller?list=current&view=home",
    )
    batch = parse_manual_import(
        _document(solicitations=[first, second]), retrieved_at=_NOW
    )

    assert batch.state is AcquisitionState.SUCCESS
    assert len(batch.solicitations) == 1
    assert batch.exact_duplicates_removed == 1
    assert batch.solicitations[0].duplicate_count == 1
    assert "title" in batch.solicitations[0].conflicting_fields


def test_normalized_url_only_flags_possible_match_when_identifiers_differ() -> None:
    first = _official_record(solicitation_id="SYN-001")
    second = _official_record(
        solicitation_id="SYN-002",
        url=MANATEE_BIDS_URL + "?utm_source=manual",
    )
    batch = parse_manual_import(
        _document(solicitations=[first, second]), retrieved_at=_NOW
    )

    assert len(batch.solicitations) == 2
    assert batch.exact_duplicates_removed == 0
    assert batch.possible_url_matches == (("SYN-001", "SYN-002"),)


def test_malformed_source_response_fails_closed() -> None:
    malformed = _document()
    malformed["unrecognized"] = True
    batch = parse_manual_import(malformed, retrieved_at=_NOW)

    assert batch.state is AcquisitionState.MALFORMED
    assert batch.malformed_reason is not None
    assert batch.solicitations == ()


def test_deadline_is_only_expired_after_primary_source_verification() -> None:
    deadline = date(2026, 11, 8)
    assert (
        deadline_disposition(
            deadline,
            primary_source_verified=False,
            as_of=date(2026, 11, 9),
        )
        == "UNVERIFIED"
    )
    assert (
        deadline_disposition(
            deadline,
            primary_source_verified=True,
            as_of=date(2026, 11, 9),
        )
        == "EXPIRED"
    )
    assert (
        deadline_disposition(
            date(2026, 11, 20),
            primary_source_verified=True,
            as_of=date(2026, 11, 9),
        )
        == "NOT_EXPIRED"
    )
