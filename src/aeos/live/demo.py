r"""Run the deterministic LIVE business assessment against fictional fixtures.

From the repository root in PowerShell, run
``$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m aeos.live.demo``.
"""

from datetime import datetime, timezone
import argparse
import json
from collections.abc import Sequence

from aeos.application.live import assess_business, render_assessment_summary
from aeos.live.domain import (
    BusinessAssessment,
    BusinessInput,
    EvidenceKind,
    JsonScalar,
    MarketEntity,
    MarketEntityType,
    SourceEvidence,
    assessment_to_dict,
)
from aeos.live.ports import (
    MarketDiscoveryResult,
    WebsiteInspectionResult,
    WebsiteSignal,
)

_FIXTURE_TIME = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
_FIXTURE_SOURCE = "Fictional local directory fixture"


def _market_entity(
    entity_id: str,
    name: str,
    entity_type: MarketEntityType,
    category: str,
    *,
    city: str,
    state: str,
    rating: float | None = None,
    review_count: int | None = None,
    services: tuple[str, ...] = (),
) -> tuple[MarketEntity, tuple[SourceEvidence, ...]]:
    """Create a fictional listing whose every field has owned source evidence."""

    observed_fields: list[tuple[str, JsonScalar]] = [
        ("category", category),
        ("city", city),
        ("state", state),
    ]
    if rating is not None:
        observed_fields.append(("rating", rating))
    if review_count is not None:
        observed_fields.append(("review_count", review_count))
    observed_fields.extend(("services", service) for service in services)
    evidence = tuple(
        SourceEvidence(
            evidence_id=f"demo:{entity_id}:{field}:{index}",
            kind=EvidenceKind.OBSERVED,
            subject=name,
            field=field,
            value=value,
            source_name=_FIXTURE_SOURCE,
            retrieved_at=_FIXTURE_TIME,
            excerpt=f"Fictional demonstration listing reports {field} = {value}.",
            owner_entity_id=entity_id,
        )
        for index, (field, value) in enumerate(observed_fields)
    )
    entity = MarketEntity(
        entity_id=entity_id,
        name=name,
        entity_type=entity_type,
        category=category,
        city=city,
        state=state,
        rating=rating,
        review_count=review_count,
        services=services,
        evidence_ids=tuple(item.evidence_id for item in evidence),
    )
    return entity, evidence


def _discovery(
    *fixtures: tuple[MarketEntity, tuple[SourceEvidence, ...]],
) -> MarketDiscoveryResult:
    return MarketDiscoveryResult(
        entities=tuple(entity for entity, _ in fixtures),
        evidence=tuple(item for _, records in fixtures for item in records),
        limitations=("All market listings are fictional demonstration data.",),
    )


def _business_evidence(
    business: BusinessInput, field: str, value: JsonScalar
) -> SourceEvidence:
    return SourceEvidence(
        evidence_id=f"demo:{business.business_name}:{field}",
        kind=EvidenceKind.OBSERVED,
        subject=business.business_name,
        field=field,
        value=value,
        source_name="Fictional public listing fixture",
        retrieved_at=_FIXTURE_TIME,
        excerpt=f"Fictional demonstration listing reports {field} = {value}.",
    )


def _hvac_assessment() -> BusinessAssessment:
    business = BusinessInput(
        business_name="Sunrise Home Comfort (Fictional)",
        industry="HVAC",
        city="Orlando",
        state="Florida",
        website_url="https://sunrise-hvac.example",
        monthly_inquiries=32,
        monthly_quotes=25,
        monthly_jobs=17,
        has_structured_follow_up=False,
        notes="Fictional demonstration input; not a real company.",
    )
    discovery = _discovery(
        _market_entity(
            "hvac-competitor-lake",
            "Lakeview Climate (Fictional)",
            MarketEntityType.COMPETITOR,
            "HVAC",
            city="Orlando",
            state="Florida",
            rating=4.7,
            review_count=91,
            services=("repair", "maintenance"),
        ),
        _market_entity(
            "hvac-competitor-orange",
            "Orange Grove Heating (Fictional)",
            MarketEntityType.COMPETITOR,
            "HVAC",
            city="Orlando",
            state="Florida",
            rating=4.4,
            review_count=54,
            services=("installation", "repair"),
        ),
        _market_entity(
            "hvac-prospect-property",
            "Palmetto Property Group (Fictional)",
            MarketEntityType.POTENTIAL_CUSTOMER,
            "property managers",
            city="Orlando",
            state="Florida",
        ),
        _market_entity(
            "hvac-partner-contractors",
            "Cypress General Contractors (Fictional)",
            MarketEntityType.PARTNER,
            "general contractors",
            city="Orlando",
            state="Florida",
        ),
        _market_entity(
            "hvac-supplier-equipment",
            "Sunstate Equipment Supply (Fictional)",
            MarketEntityType.SUPPLIER,
            "equipment distributors",
            city="Orlando",
            state="Florida",
        ),
    )
    website_signal = WebsiteSignal(
        field="quote_request_path",
        value=False,
        evidence_id="demo:sunrise:website:quote-request",
    )
    website = WebsiteInspectionResult(
        signals=(website_signal,),
        evidence=(
            SourceEvidence(
                evidence_id=website_signal.evidence_id,
                kind=EvidenceKind.OBSERVED,
                subject=business.business_name,
                field=website_signal.field,
                value=website_signal.value,
                source_name="Fictional website inspection fixture",
                retrieved_at=_FIXTURE_TIME,
                excerpt="The fictional inspected page has no quote request path.",
            ),
        ),
    )
    target_evidence = (
        _business_evidence(business, "rating", 4.6),
        _business_evidence(business, "review_count", 38),
    )
    return assess_business(
        business,
        discovery,
        evidence=target_evidence,
        website_inspection=website,
    )


def _cleaning_assessment() -> BusinessAssessment:
    business = BusinessInput(
        business_name="Cedar & Coast Cleaning (Fictional)",
        industry="House Cleaning",
        city="Port Mason",
        state="Oregon",
        website_url=None,
        monthly_inquiries=24,
        monthly_quotes=18,
        monthly_jobs=12,
        has_structured_follow_up=False,
        notes="Fictional demonstration input; this business has no website.",
    )
    discovery = _discovery(
        _market_entity(
            "cleaning-competitor-compass",
            "Compass Home Cleaning (Fictional)",
            MarketEntityType.COMPETITOR,
            "house cleaning",
            city="Port Mason",
            state="Oregon",
            rating=4.6,
            review_count=86,
            services=("recurring cleaning",),
        ),
        _market_entity(
            "cleaning-competitor-bright",
            "Bright Broom Co. (Fictional)",
            MarketEntityType.COMPETITOR,
            "house cleaning",
            city="Port Mason",
            state="Oregon",
            rating=4.8,
            review_count=43,
            services=("move-out cleaning",),
        ),
        _market_entity(
            "cleaning-competitor-neat",
            "Neat Nest Services (Fictional)",
            MarketEntityType.COMPETITOR,
            "house cleaning",
            city="Port Mason",
            state="Oregon",
            rating=4.5,
            review_count=61,
            services=("recurring cleaning", "move-out cleaning"),
        ),
        _market_entity(
            "cleaning-prospect-harborview",
            "Harborview Apartments (Fictional)",
            MarketEntityType.POTENTIAL_CUSTOMER,
            "apartment communities",
            city="Port Mason",
            state="Oregon",
        ),
        _market_entity(
            "cleaning-prospect-mason-bay",
            "Mason Bay Stays (Fictional)",
            MarketEntityType.POTENTIAL_CUSTOMER,
            "vacation rental managers",
            city="Port Mason",
            state="Oregon",
        ),
        _market_entity(
            "cleaning-partner-keyturn",
            "KeyTurn Realty (Fictional)",
            MarketEntityType.PARTNER,
            "real estate agencies",
            city="Port Mason",
            state="Oregon",
        ),
        _market_entity(
            "cleaning-partner-movers",
            "Tideway Movers (Fictional)",
            MarketEntityType.PARTNER,
            "moving companies",
            city="Port Mason",
            state="Oregon",
        ),
        _market_entity(
            "cleaning-supplier-mason",
            "Mason Janitorial Supply (Fictional)",
            MarketEntityType.SUPPLIER,
            "janitorial supply",
            city="Port Mason",
            state="Oregon",
        ),
        _market_entity(
            "cleaning-supplier-cleanpro",
            "CleanPro Distribution (Fictional)",
            MarketEntityType.SUPPLIER,
            "cleaning supply distributors",
            city="Port Mason",
            state="Oregon",
        ),
    )
    return assess_business(business, discovery)


def build_demo_assessments() -> tuple[BusinessAssessment, BusinessAssessment]:
    """Run the same application use case for HVAC and house-cleaning fixtures."""

    return _hvac_assessment(), _cleaning_assessment()


def build_demo_assessment() -> BusinessAssessment:
    """Preserve the original fixture helper for the no-website cleaning example."""

    return build_demo_assessments()[1]


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="write both assessments as JSON"
    )
    args = parser.parse_args(argv)
    assessments = build_demo_assessments()
    if args.json:
        print(
            json.dumps(
                {
                    "notice": "FICTIONAL DEMONSTRATION DATA ONLY; no external services or real business listings are used.",
                    "assessments": [assessment_to_dict(item) for item in assessments],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print("AEOS LIVE — FICTIONAL DEMONSTRATION DATA ONLY")
    print("No external services or real business listings are used.")
    print(
        "PowerShell command: $env:PYTHONPATH='src'; "
        r".\.venv\Scripts\python.exe -m aeos.live.demo"
    )
    print("JSON option: add --json to the module command.")
    for assessment in assessments:
        business = assessment.business
        website = business.website_url or "none supplied"
        entity_counts = {
            kind.value: sum(
                entity.entity_type is kind for entity in assessment.market_entities
            )
            for kind in MarketEntityType
        }
        print("\n" + "=" * 72)
        print(f"Fictional input: {business.business_name}")
        print(
            f"Industry and area: {business.industry} — {business.city}, {business.state}"
        )
        print(f"Website input: {website}")
        print(f"Discovered entity counts: {entity_counts}")
        print("Application assessment:")
        print(render_assessment_summary(assessment))


if __name__ == "__main__":
    main()
