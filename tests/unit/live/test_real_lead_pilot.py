from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

import aeos.live.real_lead_pilot as real_lead_pilot
from aeos.live.real_lead_pilot import (
    DEFAULT_FEASIBILITY,
    DEFAULT_PROFILE,
    redact_personal_data,
    run_pilot,
)
from aeos.live.domain.errors import InvalidLiveContract


AS_OF = date(2026, 11, 7)


def _candidate(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_platform": "Facebook public Groups and Marketplace",
        "access_method": "PUBLIC_PAGE_MANUAL",
        "demand_type": "DIRECT_CUSTOMER_DEMAND",
        "publication_date": "2026-11-06",
        "service_requested": "Residential cleaning",
        "summary": "Raw source text is deliberately ignored.",
        "source_url": "https://manual-source.aeos/community/sample-city-two/one",
        "source_event_ref": None,
        "city": "Sample City Two",
        "state": "FL",
        "explicit_intent": True,
        "is_open": True,
        "response_method": "Raw response path is replaced.",
        "publicly_accessible": True,
        "business_authorized": True,
        "source_provenance": "SYNTHETIC",
        "account_holder_authorized": False,
        "permission_basis": "PUBLIC_NOTICE",
        "source_terms_note": "Raw source terms note is replaced.",
        "procurement_status": None,
        "official_deadline": None,
        "eligibility_requirements": [],
        "expected_jobs_per_day": 1,
        "ongoing_need": False,
        "limitations": [],
        "evidence": [
            {
                "field": "city",
                "value": "Sample City Two",
                "kind": "OBSERVED",
                "confidence": 0.95,
                "excerpt": "Sample City Two",
            },
            {
                "field": "state",
                "value": "FL",
                "kind": "OBSERVED",
                "confidence": 0.95,
                "excerpt": "Example Region",
            },
            {
                "field": "service_requested",
                "value": "Residential cleaning",
                "kind": "OBSERVED",
                "confidence": 0.95,
                "excerpt": "Looking for a cleaner",
            },
            {
                "field": "explicit_intent",
                "value": True,
                "kind": "OBSERVED",
                "confidence": 0.95,
                "excerpt": "Please hire a cleaner",
            },
            {
                "field": "publication_date",
                "value": "2026-11-06",
                "kind": "OBSERVED",
                "confidence": 0.95,
            },
            {
                "field": "open_status",
                "value": True,
                "kind": "OBSERVED",
                "confidence": 0.95,
                "excerpt": "Still open",
            },
            {
                "field": "response_method",
                "value": "Raw response path is replaced.",
                "kind": "OBSERVED",
                "confidence": 0.95,
            },
        ],
    }
    payload.update(overrides)
    values = {
        "city": payload.get("city"),
        "state": payload.get("state"),
        "service_requested": payload.get("service_requested"),
        "explicit_intent": payload.get("explicit_intent"),
        "open_status": payload.get("is_open"),
        "publication_date": payload.get("publication_date"),
    }
    evidence = payload["evidence"]
    assert isinstance(evidence, list)
    for item in evidence:
        assert isinstance(item, dict)
        if item.get("field") in values:
            item["value"] = values[item["field"]]
    for field in (
        "procurement_scope",
        "eligibility_reviewed",
        "expected_jobs_per_day",
        "issuing_organization",
        "contract_duration",
        "required_insurance",
    ):
        if field in overrides:
            evidence.append(
                {
                    "field": field,
                    "value": overrides[field],
                    "kind": "OBSERVED",
                    "confidence": 0.95,
                }
            )
    if payload.get("procurement_status"):
        evidence.append(
            {
                "field": "procurement_status",
                "value": payload["procurement_status"],
                "kind": "OBSERVED",
                "confidence": 0.95,
            }
        )
    return payload


def _verified_candidate(**overrides: object) -> dict[str, object]:
    """Keep a synthetic fixture synthetic even when it has detailed claims."""

    return _candidate(**overrides)


def _run_candidates(
    tmp_path: Path, candidates: list[dict[str, object]], **kwargs: object
) -> dict[str, object]:
    candidate_file = tmp_path / "candidates.json"
    candidate_file.write_text(json.dumps({"candidates": candidates}), encoding="utf-8")
    profile_payload = json.loads(DEFAULT_PROFILE.read_text(encoding="utf-8"))
    assert isinstance(profile_payload, dict)
    profile = profile_payload.get("business_profile")
    assert isinstance(profile, dict)
    profile["business_model"] = "B2B2C"
    profile["state_region"] = "FL"
    profile["base_capacity_jobs_per_day"] = 2
    profile["expanded_capacity_jobs_per_day"] = 4
    profile["primary_services"] = [
        *profile["primary_services"],
        "Residential cleaning",
        "Commercial cleaning",
    ]
    profile["owner_confirmed_service_areas"] = [
        "Sample City One, FL",
        "Sample City Two, FL",
    ]
    profile_path = tmp_path / "business-profile.json"
    profile_path.write_text(json.dumps(profile_payload), encoding="utf-8")
    return run_pilot(
        candidate_file=candidate_file,
        output_dir=tmp_path / "out",
        store_path=tmp_path / "store.json",
        feasibility_path=DEFAULT_FEASIBILITY,
        profile_path=profile_path,
        as_of=AS_OF,
        confirm_import=bool(kwargs.get("confirm_import", False)),
    )


def test_query_plan_uses_selected_vertical_services_and_markets(tmp_path: Path) -> None:
    profile_payload = json.loads(DEFAULT_PROFILE.read_text(encoding="utf-8"))
    assert isinstance(profile_payload, dict)
    profile = profile_payload.get("business_profile")
    assert isinstance(profile, dict)
    profile.update(
        {
            "business_name": "Synthetic HVAC example",
            "industry": "HVAC",
            "vertical": "HVAC",
            "city": "North Example City",
            "state_region": "Example Region",
            "primary_services": ["Air conditioning repair"],
            "secondary_services": ["Preventive HVAC maintenance"],
            "owner_confirmed_service_areas": ["North Example City"],
            "additional_service_areas": [],
        }
    )
    profile_path = tmp_path / "hvac-profile.json"
    profile_path.write_text(json.dumps(profile_payload), encoding="utf-8")
    result = run_pilot(
        candidate_file=None,
        output_dir=tmp_path / "out",
        store_path=tmp_path / "store.json",
        feasibility_path=DEFAULT_FEASIBILITY,
        profile_path=profile_path,
        as_of=AS_OF,
        confirm_import=False,
    )
    plan = json.loads((Path(str(result["output_dir"])) / "query-plan.json").read_text())

    assert len(plan) == 2
    assert {row["vertical"] for row in plan} == {"HVAC"}
    assert {row["city"] for row in plan} == {"North Example City"}
    assert {row["service"] for row in plan} == {
        "Air conditioning repair",
        "Preventive HVAC maintenance",
    }


@pytest.mark.parametrize(
    ("overrides", "classification"),
    [
        ({}, "HOT"),
        (
            {
                "service_requested": "Vacation rental turnover cleaning",
                "source_url": "https://manual-source.aeos/community/sample-city-two/airbnb",
            },
            "HOT",
        ),
        (
            {
                "service_requested": "Commercial cleaning",
                "source_url": "https://manual-source.aeos/community/sample-city-two/office",
            },
            "HOT",
        ),
        ({"publication_date": "2026-07-01"}, "EXPIRED"),
        (
            {
                "demand_type": "RECOMMENDATION_SIGNAL",
                "explicit_intent": False,
                "is_open": None,
                "source_url": "https://manual-source.aeos/community/sample-city-two/recommendation",
            },
            "COLD",
        ),
        (
            {
                "city": "Sample City Nine",
                "source_url": "https://manual-source.aeos/community/sample-city-two/sample-city-nine",
            },
            "COLD",
        ),
        (
            {
                "service_requested": "Carpet installation",
                "source_url": "https://manual-source.aeos/community/sample-city-two/unsupported",
            },
            "COLD",
        ),
        ({"publication_date": None}, "INSUFFICIENT_EVIDENCE"),
        (
            {"business_authorized": False, "permission_basis": "NOT_APPROVED"},
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            {
                "demand_type": "PUBLIC_PROCUREMENT",
                "procurement_status": "OPEN_SOLICITATION",
                "is_open": True,
                "expected_jobs_per_day": None,
                "source_url": "https://manual-source.aeos/procurement/sample-city-two/project/open-cleaning",
            },
            "WARM",
        ),
        (
            {
                "demand_type": "PUBLIC_PROCUREMENT",
                "procurement_status": "AWARD_NOTICE",
                "is_open": False,
                "source_url": "https://manual-source.aeos/procurement/sample-city-two/project/award-cleaning",
            },
            "EXPIRED",
        ),
        (
            {
                "expected_jobs_per_day": 3,
                "source_url": "https://manual-source.aeos/community/sample-city-two/over-capacity",
            },
            "WARM",
        ),
    ],
)
def test_candidates_use_existing_opportunity_qualification(
    tmp_path: Path, overrides: dict[str, object], classification: str
) -> None:
    result = _run_candidates(tmp_path, [_verified_candidate(**overrides)])
    saved = json.loads((tmp_path / "out" / "opportunities.json").read_text())
    assert result["candidate_count"] == 1
    assert saved[0]["classification"] == classification
    if overrides.get("expected_jobs_per_day") == 3:
        assert saved[0]["capacity_review_required"] is True


def test_cross_platform_possible_duplicate_is_held_for_review(tmp_path: Path) -> None:
    left = _verified_candidate(
        source_platform="Facebook public Groups and Marketplace",
        source_url="https://manual-source.aeos/community/sample-city-two/1",
    )
    right = _verified_candidate(
        source_platform="Reddit public communities and Data API",
        source_url="https://manual-source.aeos/community/sample-city-two/2",
    )
    result = _run_candidates(tmp_path, [left, right])
    saved = json.loads((tmp_path / "out" / "opportunities.json").read_text())
    assert result["candidate_count"] == 2
    assert saved[1]["duplicate_preview"]["result"] == "NEEDS_REVIEW"


def test_procurement_brief_keeps_public_notice_details(tmp_path: Path) -> None:
    candidate = _verified_candidate(
        source_platform="City of Sample City One and City of Sample City Two OpenGov procurement portals",
        demand_type="PUBLIC_PROCUREMENT",
        service_requested="Commercial cleaning",
        source_url="https://manual-source.aeos/procurement/sample-city-two/project/123",
        procurement_status="OPEN_SOLICITATION",
        solicitation_id="RFP-26-1",
        issuing_organization="City of Sample City Two",
        procurement_scope="Recurring janitorial service for one office",
        eligibility_requirements=["Vendor registration required"],
        eligibility_reviewed=False,
        contract_duration="One year",
        required_insurance="General liability certificate",
        expected_jobs_per_day=None,
    )
    result = _run_candidates(tmp_path, [candidate])
    saved = json.loads((tmp_path / "out" / "opportunities.json").read_text())[0]
    report = (tmp_path / "out" / "acquisition-report-es.md").read_text(encoding="utf-8")
    assert result["candidate_count"] == 1
    assert saved["solicitation_id"] == "RFP-26-1"
    assert saved["issuing_organization"] == "City of Sample City Two"
    assert saved["contract_duration"] == "One year"
    assert "RFP-26-1" in report


def test_inaccessible_candidate_is_rejected_without_empty_market_claim(
    tmp_path: Path,
) -> None:
    candidate = _verified_candidate(source_accessible=False)
    result = _run_candidates(tmp_path, [candidate])
    report = (tmp_path / "out" / "acquisition-report-es.md").read_text(encoding="utf-8")
    assert result["candidate_count"] == 0
    assert result["rejected_count"] == 1
    assert "**no** significa que el mercado carezca de demanda" in report


def test_source_text_with_personal_details_is_omitted_before_reports(
    tmp_path: Path,
) -> None:
    candidate = _verified_candidate()
    evidence = candidate["evidence"]
    assert isinstance(evidence, list)
    assert isinstance(evidence[0], dict)
    evidence[0]["excerpt"] = (
        "Contact: Sample Person, 202-555-0199, sample.person@fixture.example, @sample, 100 Example Street"
    )
    result = _run_candidates(tmp_path, [candidate])
    outputs = "".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "out").glob("*")
        if path.suffix in {".json", ".md"}
    )
    assert result["candidate_count"] == 1
    assert "Sample Person" not in outputs
    assert "202-555-0199" not in outputs
    assert "sample.person@fixture.example" not in outputs
    assert "@sample" not in outputs
    assert "100 Example Street" not in outputs


def test_redaction_helper_removes_common_contact_details() -> None:
    redacted = redact_personal_data(
        "Contact: Sample Person at 202-555-0199 or sample.person@fixture.example; @sample, 100 Example Street"
    )
    assert "Sample Person" not in redacted
    assert "202-555-0199" not in redacted
    assert "sample.person@fixture.example" not in redacted
    assert "@sample" not in redacted
    assert "100 Example Street" not in redacted


def test_provider_diagnostics_report_missing_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AEOS_SAM_GOV_API_KEY", raising=False)
    result = _run_candidates(tmp_path, [])
    diagnostics = json.loads(
        (tmp_path / "out" / "provider-diagnostics.json").read_text()
    )
    sam = next(
        item for item in diagnostics["sources"] if item["source_id"] == "sam_gov"
    )
    thumbtack = next(
        item
        for item in diagnostics["sources"]
        if item["source_id"] == "thumbtack_self_serve"
    )
    assert result["candidate_count"] == 0
    assert sam["status"] == "PROVIDER_NOT_CONFIGURED"
    assert sam["configured"] is False
    assert thumbtack["status"] == "FIXTURE_ONLY"
    assert diagnostics["network_requests"] == 0


def test_preview_does_not_create_or_modify_persistent_inbox(tmp_path: Path) -> None:
    store = tmp_path / "store.json"
    candidate_file = tmp_path / "candidate.json"
    candidate_file.write_text(
        json.dumps({"candidates": [_verified_candidate()]}), encoding="utf-8"
    )
    run_pilot(
        candidate_file=candidate_file,
        output_dir=tmp_path / "preview",
        store_path=store,
        feasibility_path=DEFAULT_FEASIBILITY,
        as_of=AS_OF,
        confirm_import=False,
    )
    assert not store.exists()


def test_persistent_import_requires_confirmation_and_tenant_attestation(
    tmp_path: Path,
) -> None:
    candidate_file = tmp_path / "candidate.json"
    candidate_file.write_text(
        json.dumps({"candidates": [_verified_candidate()]}), encoding="utf-8"
    )
    store = tmp_path / "persistent-store.json"
    run_pilot(
        candidate_file=candidate_file,
        output_dir=tmp_path / "preview",
        store_path=store,
        feasibility_path=DEFAULT_FEASIBILITY,
        as_of=AS_OF,
        confirm_import=False,
    )
    assert not store.exists()
    result = run_pilot(
        candidate_file=candidate_file,
        output_dir=tmp_path / "imported",
        store_path=store,
        feasibility_path=DEFAULT_FEASIBILITY,
        as_of=AS_OF,
        confirm_import=True,
    )
    assert result["imported"] is False
    assert result["rejected_count"] == 1
    assert not store.exists()


@pytest.mark.parametrize(
    "source_url",
    [
        "https://example.org/requests/synthetic",
        "https://example.org\u3002/requests/synthetic",
    ],
)
def test_synthetic_example_org_with_business_authorization_is_rejected(
    tmp_path: Path, source_url: str
) -> None:
    candidate = _candidate(
        source_url=source_url,
        business_authorized=True,
    )
    assert "template_only" not in candidate
    result = _run_candidates(tmp_path, [candidate], confirm_import=True)
    assert result["candidate_count"] == 0
    assert result["rejected_count"] == 1
    assert result["imported"] is False
    assert not (tmp_path / "store.json").exists()


def test_synthetic_record_without_template_marker_cannot_be_imported(
    tmp_path: Path,
) -> None:
    candidate = _candidate()
    result = _run_candidates(tmp_path, [candidate], confirm_import=True)
    output = json.loads((tmp_path / "out" / "opportunities.json").read_text())
    assert "template_only" not in candidate
    assert result["candidate_count"] == 1
    assert result["rejected_count"] == 1
    assert result["imported"] is False
    assert output[0]["source_provenance"] == "SYNTHETIC"
    assert output[0]["classification"] == "HOT"
    assert output[0]["evaluation_mode"] == "SYNTHETIC_PREVIEW"
    assert not (tmp_path / "store.json").exists()


def test_explicit_template_marker_is_rejected(tmp_path: Path) -> None:
    result = _run_candidates(
        tmp_path, [_verified_candidate(template_only=True)], confirm_import=True
    )
    assert result["candidate_count"] == 0
    assert result["rejected_count"] == 1
    assert not (tmp_path / "store.json").exists()


def test_unknown_provenance_is_rejected_from_persistent_import(
    tmp_path: Path,
) -> None:
    result = _run_candidates(
        tmp_path,
        [_verified_candidate(source_provenance="UNKNOWN")],
        confirm_import=True,
    )
    assert result["candidate_count"] == 1
    assert result["rejected_count"] == 1
    assert result["imported"] is False
    assert not (tmp_path / "store.json").exists()


def test_rejected_synthetic_record_leaves_existing_store_unchanged(
    tmp_path: Path,
) -> None:
    store = tmp_path / "store.json"
    store.write_text(json.dumps({"schema_version": 1, "records": []}))
    before = store.read_bytes()

    result = _run_candidates(tmp_path, [_candidate()], confirm_import=True)
    assert result["imported"] is False
    assert result["rejected_count"] == 1
    assert store.read_bytes() == before


def test_synthetic_fixture_is_still_available_in_isolated_preview(
    tmp_path: Path,
) -> None:
    result = _run_candidates(tmp_path, [_candidate()])
    output = json.loads((tmp_path / "out" / "opportunities.json").read_text())
    assert result["candidate_count"] == 1
    assert result["rejected_count"] == 0
    assert output[0]["source_provenance"] == "SYNTHETIC"
    assert output[0]["classification"] == "HOT"
    assert output[0]["evaluation_mode"] == "SYNTHETIC_PREVIEW"
    assert not (tmp_path / "store.json").exists()


def test_shareable_outputs_remove_sensitive_url_parameters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "synthetic-test-secret"
    candidate = _verified_candidate(
        source_url=(
            "https://manual-source.aeos/community/sample-city-two/one"
            f"?access_token={secret}"
        )
    )

    shareable_url = "https://sources.example/report?access_token=" + secret
    monkeypatch.setattr(
        real_lead_pilot,
        "_query_plan",
        lambda *_args, **_kwargs: [{"source_url": shareable_url}],
    )

    _run_candidates(tmp_path, [candidate])

    output = json.loads((tmp_path / "out" / "opportunities.json").read_text())
    markdown = (tmp_path / "out" / "acquisition-report-es.md").read_text()
    query_plan = (tmp_path / "out" / "query-plan.json").read_text()
    assert secret not in json.dumps(output)
    assert "access_token" not in json.dumps(output)
    assert secret not in markdown
    assert "access_token" not in markdown
    assert secret not in query_plan
    assert "access_token" not in query_plan


def test_import_confirmation_requires_candidate_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidLiveContract, match="--confirm-import requires"):
        run_pilot(
            candidate_file=None,
            output_dir=tmp_path / "out",
            store_path=tmp_path / "store.json",
            feasibility_path=DEFAULT_FEASIBILITY,
            as_of=AS_OF,
            confirm_import=True,
        )
\n
def _real_profile_without_organization_id(tmp_path: Path) -> Path:
    payload = json.loads(DEFAULT_PROFILE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    profile = payload.get("business_profile")
    assert isinstance(profile, dict)
    profile["is_fictional_example"] = False
    profile.pop("organization_id", None)
    path = tmp_path / "real-profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    return path


def test_default_storage_requires_organization_id_for_real_profile(
    tmp_path: Path,
) -> None:
    profile_path = _real_profile_without_organization_id(tmp_path)
    with pytest.raises(InvalidLiveContract, match="organization_id is required"):
        run_pilot(
            candidate_file=None,
            feasibility_path=DEFAULT_FEASIBILITY,
            profile_path=profile_path,
            as_of=AS_OF,
            confirm_import=False,
        )


def test_explicit_storage_paths_allow_isolated_profile_without_organization_id(
    tmp_path: Path,
) -> None:
    profile_path = _real_profile_without_organization_id(tmp_path)
    output_dir = tmp_path / "explicit-output"
    store_path = tmp_path / "explicit-store.json"
    result = run_pilot(
        candidate_file=None,
        output_dir=output_dir,
        store_path=store_path,
        feasibility_path=DEFAULT_FEASIBILITY,
        profile_path=profile_path,
        as_of=AS_OF,
        confirm_import=False,
    )
    assert Path(str(result["output_dir"])) == output_dir
    assert (output_dir / "acquisition-report-es.md").is_file()
    assert not store_path.exists()


def test_fictional_default_storage_uses_synthetic_namespace() -> None:
    profile_payload = json.loads(DEFAULT_PROFILE.read_text(encoding="utf-8"))
    profile = real_lead_pilot.parse_business_profile_document(profile_payload)
    storage = real_lead_pilot._profile_storage_directory(profile)
    assert storage.name.startswith("synthetic-")

