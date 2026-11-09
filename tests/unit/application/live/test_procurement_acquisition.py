from datetime import date, datetime, timezone

from aeos.application.live.procurement_acquisition import (
    build_acquisition_report,
    build_synthetic_profile_preview,
    render_acquisition_markdown,
)
from aeos.live.adapters.manatee_procurement import (
    MANATEE_BIDS_URL,
    ManateeProcurementBatch,
    parse_manual_import,
)
from aeos.live.domain.profile import BusinessModel, BusinessProfile


def _blocked_candidate_batch() -> ManateeProcurementBatch:
    payload: dict[str, object] = {
        "schema_version": 1,
        "source": {
            "name": "Manatee County Bids and Proposals",
            "starting_url": MANATEE_BIDS_URL,
            "access_mode": "MANUAL_IMPORT",
            "response_state": "BLOCKED",
            "block_reason": "The official linked procurement portal returned HTTP 403.",
        },
        "solicitations": [],
        "secondary_candidates": [
            {
                "issuing_agency": "Manatee County",
                "solicitation_id": "SYN-SECONDARY-001",
                "title": "Synthetic secondary-only candidate",
                "description": None,
                "official_source_url": None,
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
                        "reference_id": "secondary-fixture",
                        "kind": "SECONDARY",
                        "url": "https://secondary.invalid/listing/1",
                        "label": "Synthetic test discovery reference",
                        "fields": ["solicitation_id", "title"],
                        "excerpt": "Synthetic test data only.",
                    }
                ],
            }
        ],
    }
    return parse_manual_import(
        payload,
        retrieved_at=datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc),
    )


def _profile(vertical: str, service: str) -> BusinessProfile:
    return BusinessProfile(
        business_name=f"Synthetic {vertical} Company",
        industry=vertical,
        vertical=vertical,
        description="Fictional fixture for a source-independent preview.",
        business_model=BusinessModel.MIXED,
        country="US",
        state_region="FL",
        city="Sample City",
        service_radius=None,
        service_radius_unit=None,
        primary_services=(service,),
        target_customer_segments=("Commercial property managers",),
        owner_confirmed_service_areas=("Sample City",),
        base_capacity_jobs_per_day=2,
        is_fictional_example=True,
    )


def test_blocked_report_keeps_secondary_candidate_pending_and_not_empty() -> None:
    report = build_acquisition_report(
        _blocked_candidate_batch(),
        as_of=date(2026, 11, 9),
        profile_status="UNAVAILABLE",
    )

    source = report["source"]
    counts = report["counts"]
    opportunities = report["opportunities"]
    assert isinstance(source, dict)
    assert isinstance(counts, dict)
    assert isinstance(opportunities, list)
    assert source["acquisition_state"] == "BLOCKED"
    assert counts["observed_by_adapter"] == 0
    assert counts["verified_against_official_source"] == 0
    assert counts["pending_review"] == 1
    assert opportunities[0]["decision"] == "PENDING_PRIMARY_SOURCE"
    assert opportunities[0]["official_source_url"] == "UNKNOWN"
    assert opportunities[0]["closing_date"] == "UNKNOWN"
    markdown = render_acquisition_markdown(report)
    assert "BLOCKED" in markdown
    assert "not an empty market" in markdown
    assert "PENDING_PRIMARY_SOURCE" in markdown


def test_existing_synthetic_preview_accepts_multiple_vertical_profiles() -> None:
    profiles = (
        _profile("HOUSE_CLEANING", "Recurring residential cleaning"),
        _profile("HVAC", "Commercial HVAC maintenance"),
        _profile("CONSTRUCTION", "Tenant improvement construction"),
    )
    previews = [
        build_synthetic_profile_preview(profile, as_of=date(2026, 11, 9))
        for profile in profiles
    ]

    assert [item["vertical"] for item in previews] == [
        "HOUSE_CLEANING",
        "HVAC",
        "CONSTRUCTION",
    ]
    assert all(item["scenario"] == "SYNTHETIC_ONLY" for item in previews)
    assert all(item["actionable"] is False for item in previews)
