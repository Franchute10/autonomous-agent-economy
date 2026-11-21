"""Product catalog regressions; all observations are isolated synthetic previews."""

from dataclasses import replace
from datetime import date, datetime, timezone
import unittest

from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.evidence import EvidenceKind, SourceEvidence
from aeos.live.domain.opportunity_inbox import (
    DemandType,
    LeadClassification,
    Opportunity,
    PermissionBasis,
    SourceProvenance,
    classify_opportunity,
    score_opportunity_preview,
)
from aeos.live.domain.profile import BusinessModel, BusinessProfile


AS_OF = date(2026, 11, 21)
NOW = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)


def profile() -> BusinessProfile:
    return BusinessProfile(
        business_name="Fictional catalog business",
        industry="Retail",
        vertical="OTHER",
        description="Synthetic product and service matching fixture.",
        business_model=BusinessModel.B2B2C,
        country="PE",
        state_region="Lima",
        city="Lima",
        service_radius=None,
        service_radius_unit=None,
        primary_services=("Delivery",),
        products=("Coffee makers",),
        target_customer_segments=("Customers",),
        owner_confirmed_service_areas=("Lima, Lima",),
        is_fictional_example=True,
    )


def request(offering: str = "Coffee makers", *, is_open: bool = True) -> Opportunity:
    values: dict[str, str | bool] = {
        "city": "Lima",
        "state": "Lima",
        "service_requested": offering,
        "publication_date": "2026-11-20",
        "explicit_intent": True,
        "open_status": is_open,
        "response_method": "Source reply form",
    }
    evidence = tuple(
        SourceEvidence(
            evidence_id=f"synthetic-{field}",
            kind=EvidenceKind.REPORTED,
            subject="synthetic-request",
            field=field,
            value=value,
            source_name="Synthetic catalog fixture",
            confidence=0.95,
            excerpt="Synthetic fixture; no real source was inspected.",
        )
        for field, value in values.items()
    )
    return Opportunity(
        opportunity_id="synthetic-request",
        title="Synthetic offering request",
        source_platform="Synthetic catalog fixture",
        demand_type=DemandType.DIRECT_CUSTOMER_DEMAND,
        publication_date=date(2026, 11, 20),
        discovered_at=NOW,
        service_requested=offering,
        summary="Offline fixture, not a real buyer.",
        source_url="https://manual-source.aeos/catalog/fixture",
        source_event_ref=None,
        city="Lima",
        state="Lima",
        explicit_intent=True,
        is_open=is_open,
        response_method="Source reply form",
        publicly_accessible=True,
        business_authorized=True,
        account_holder_authorized=False,
        permission_basis=PermissionBasis.MANUAL_ONLY,
        source_terms_note="Synthetic preview only; no real access permission asserted.",
        procurement_status=None,
        official_deadline=None,
        eligibility_requirements=(),
        expected_jobs_per_day=None,
        ongoing_need=False,
        limitations=("Synthetic preview only",),
        evidence=evidence,
        source_provenance=SourceProvenance.SYNTHETIC,
    )


class ProductOpportunityFitTests(unittest.TestCase):
    def test_product_only_profile_can_match_declared_catalog(self) -> None:
        product_only = replace(profile(), primary_services=())
        result = score_opportunity_preview(
            request(), as_of=AS_OF, organization_profile=product_only
        )
        self.assertEqual(result.classification, LeadClassification.HOT)

    def test_mixed_profile_matches_catalog_without_service_alias(self) -> None:
        result = score_opportunity_preview(
            request(), as_of=AS_OF, organization_profile=profile()
        )
        self.assertEqual(result.classification, LeadClassification.HOT)

    def test_unlisted_product_remains_cold(self) -> None:
        result = score_opportunity_preview(
            request("Refrigerators"), as_of=AS_OF, organization_profile=profile()
        )
        self.assertEqual(result.classification, LeadClassification.COLD)

    def test_catalog_match_does_not_override_geography(self) -> None:
        other_market = replace(profile(), owner_confirmed_service_areas=("Cusco, Cusco",))
        result = score_opportunity_preview(
            request(), as_of=AS_OF, organization_profile=other_market
        )
        self.assertEqual(result.classification, LeadClassification.COLD)

    def test_closed_product_request_remains_expired(self) -> None:
        result = score_opportunity_preview(
            request(is_open=False), as_of=AS_OF, organization_profile=profile()
        )
        self.assertEqual(result.classification, LeadClassification.EXPIRED)

    def test_matching_synthetic_product_cannot_become_a_real_lead(self) -> None:
        result = classify_opportunity(
            request(), as_of=AS_OF, organization_profile=profile()
        )
        self.assertEqual(result.classification, LeadClassification.INSUFFICIENT_EVIDENCE)

    def test_existing_service_match_is_preserved(self) -> None:
        result = score_opportunity_preview(
            request("Delivery"), as_of=AS_OF, organization_profile=profile()
        )
        self.assertEqual(result.classification, LeadClassification.HOT)

    def test_known_empty_offering_is_still_invalid(self) -> None:
        with self.assertRaises(InvalidLiveContract):
            replace(profile(), primary_services=(), products=())


if __name__ == "__main__":
    unittest.main()
