from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest

from aeos.live.demo import build_demo_assessment, build_demo_assessments
from aeos.live.domain import (
    AssessmentStatus,
    BestNextMove,
    BusinessAssessment,
    BusinessInput,
    EvidenceKind,
    InvalidLiveContract,
    MarketEntity,
    MarketEntityType,
    MarketPosition,
    Opportunity,
    OpportunityType,
    SourceEvidence,
    Vertical,
    assessment_to_dict,
    assessment_to_json,
    vertical_profile_for,
)
from aeos.live.ports import MarketDiscoveryResult


def _evidence(**changes: object) -> SourceEvidence:
    values: dict[str, object] = {
        "evidence_id": "evidence-1",
        "kind": EvidenceKind.OBSERVED,
        "subject": "a source",
        "field": "rating",
        "value": 4.5,
        "source_name": "fictional fixture",
    }
    values.update(changes)
    return SourceEvidence(**values)  # type: ignore[arg-type]


def _opportunity(**changes: object) -> Opportunity:
    values: dict[str, object] = {
        "opportunity_id": "opportunity-1",
        "opportunity_type": OpportunityType.FOLLOW_UP,
        "title": "Follow up",
        "description": "Contact recent quote recipients.",
        "evidence_ids": ("evidence-1",),
        "impact": 3,
        "confidence": 3,
        "evidence_strength": 3,
        "executability": 3,
        "effort": 3,
        "time_to_value": "one week",
        "recommended_action": "Send a short message.",
    }
    values.update(changes)
    return Opportunity(**values)  # type: ignore[arg-type]


def _assessment(**changes: object) -> BusinessAssessment:
    values: dict[str, object] = {
        "business": BusinessInput(
            "Test Cleaning", "House Cleaning", "Port Mason", "OR"
        ),
        "evidence": (_evidence(),),
        "market_entities": (),
        "market_position": MarketPosition(),
        "market_structure_observations": (),
        "opportunities": (_opportunity(),),
        "best_next_move": BestNextMove(
            "opportunity-1",
            "It is actionable.",
            ("evidence-1",),
            "Send a message.",
            "Replies received within seven days",
            (),
        ),
        "limitations": (),
    }
    values.update(changes)
    return BusinessAssessment(**values)  # type: ignore[arg-type]


def test_business_input_validates_required_fields_and_preserves_unknowns() -> None:
    business = BusinessInput("  Local Cleaning ", "House Cleaning", "Port Mason", "OR")
    assert business.business_name == "Local Cleaning"
    assert business.country == "US"
    assert business.website_url is None
    assert business.monthly_inquiries is None
    assert business.average_job_value is None
    assert business.monthly_inquiries != 0
    with pytest.raises(InvalidLiveContract):
        BusinessInput(" ", "House Cleaning", "Port Mason", "OR")
    with pytest.raises(InvalidLiveContract):
        BusinessInput("Business", "Cleaning", "City", "ST", monthly_jobs=-1)
    with pytest.raises(InvalidLiveContract):
        BusinessInput("Business", "Cleaning", "City", "ST", monthly_jobs=True)
    with pytest.raises(InvalidLiveContract):
        BusinessInput("Business", "Cleaning", "City", "ST", repeat_customer_share=1.1)


def test_business_input_works_without_a_website_and_is_immutable() -> None:
    business = BusinessInput("Clean Co", "House Cleaning", "Town", "OR")
    assert business.website_url is None
    with pytest.raises(FrozenInstanceError):
        business.website_url = "https://example.com"  # type: ignore[misc]


def test_evidence_kinds_are_explicit_and_estimates_keep_assumptions() -> None:
    assert {kind.value for kind in EvidenceKind} == {
        "OBSERVED",
        "REPORTED",
        "INFERRED",
        "ESTIMATED",
    }
    estimated = _evidence(
        kind=EvidenceKind.ESTIMATED,
        assumptions=("assumption one", "assumption two"),
    )
    assert estimated.assumptions == ("assumption one", "assumption two")
    with pytest.raises(InvalidLiveContract, match="assumptions"):
        _evidence(kind=EvidenceKind.ESTIMATED)
    with pytest.raises(InvalidLiveContract):
        _evidence(kind="OBSERVED")
    with pytest.raises(InvalidLiveContract):
        _evidence(retrieved_at=datetime(2026, 1, 1))


@pytest.mark.parametrize(
    "value",
    ["evidence text", 12, 4.5, True, False, None],
    ids=["string", "integer", "float", "true", "false", "none"],
)
def test_source_evidence_accepts_and_serializes_exact_json_scalars(
    value: object,
) -> None:
    evidence = _evidence(value=value)
    assessment = _assessment(evidence=(evidence,))

    serialized_value = json.loads(assessment_to_json(assessment))["evidence"][0][
        "value"
    ]
    assert serialized_value == value
    assert type(serialized_value) is type(value)


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        b"bytes",
        Decimal("1.25"),
        1 + 2j,
        object(),
        ["value"],
        {"value": "nested"},
        ("value",),
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
    ids=[
        "datetime",
        "bytes",
        "decimal",
        "complex",
        "arbitrary-object",
        "list",
        "dict",
        "tuple",
        "nan",
        "positive-infinity",
        "negative-infinity",
    ],
)
def test_source_evidence_rejects_invalid_values_during_construction(
    value: object,
) -> None:
    with pytest.raises(InvalidLiveContract, match="JSON scalar|finite"):
        _evidence(value=value)


def test_retrieved_timestamp_is_normalized_to_utc() -> None:
    local_time = datetime(2026, 1, 1, 7, 0, tzinfo=timezone(timedelta(hours=-5)))

    evidence = _evidence(retrieved_at=local_time)

    assert evidence.retrieved_at == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert evidence.retrieved_at is not None
    assert evidence.retrieved_at.tzinfo is timezone.utc


def test_market_entity_types_and_optional_rating_fields() -> None:
    assert {kind.value for kind in MarketEntityType} == {
        "COMPETITOR",
        "POTENTIAL_CUSTOMER",
        "PARTNER",
        "SUPPLIER",
    }
    entity = MarketEntity("comp-1", "Fictional competitor", MarketEntityType.COMPETITOR)
    assert entity.rating is None
    assert entity.review_count is None
    assert entity.entity_type is MarketEntityType.COMPETITOR
    with pytest.raises(InvalidLiveContract):
        MarketEntity(
            "comp-2", "Invalid rating", MarketEntityType.COMPETITOR, rating=5.1
        )
    with pytest.raises(InvalidLiveContract):
        MarketEntity(
            "comp-3", "Invalid count", MarketEntityType.COMPETITOR, review_count=-1
        )


def test_opportunity_score_dimensions_are_limited_to_one_through_five() -> None:
    assert _opportunity().impact == 3
    for field in (
        "impact",
        "confidence",
        "evidence_strength",
        "executability",
        "effort",
    ):
        with pytest.raises(InvalidLiveContract):
            _opportunity(**{field: 0})
        with pytest.raises(InvalidLiveContract):
            _opportunity(**{field: 6})


def test_best_next_move_must_reference_existing_opportunity() -> None:
    best_next_move = _assessment().best_next_move
    assert best_next_move is not None
    assert best_next_move.selected_opportunity_id == "opportunity-1"
    with pytest.raises(InvalidLiveContract, match="existing opportunity"):
        _assessment(
            best_next_move=BestNextMove(
                "missing",
                "reason",
                ("evidence-1",),
                "action",
                "KPI",
                (),
            )
        )


def test_best_next_move_evidence_must_support_selected_opportunity() -> None:
    with pytest.raises(InvalidLiveContract, match="must support its selected"):
        _assessment(
            evidence=(
                _evidence(),
                _evidence(evidence_id="evidence-2", field="other"),
            ),
            opportunities=(_opportunity(evidence_ids=("evidence-2",)),),
        )


def test_insufficient_data_assessment_has_no_recommendation() -> None:
    assessment = _assessment(
        evidence=(),
        opportunities=(),
        best_next_move=None,
        limitations=("Not enough attributable market evidence.",),
        status=AssessmentStatus.INSUFFICIENT_DATA,
    )

    assert assessment.status is AssessmentStatus.INSUFFICIENT_DATA
    assert assessment.best_next_move is None
    assert assessment.opportunities == ()
    assert json.loads(assessment_to_json(assessment))["status"] == "INSUFFICIENT_DATA"


def test_ready_assessment_requires_evidence() -> None:
    with pytest.raises(InvalidLiveContract, match="requires evidence"):
        _assessment(evidence=())


def test_aggregate_rejects_invalid_evidence_references() -> None:
    with pytest.raises(InvalidLiveContract, match="unknown evidence"):
        _assessment(opportunities=(_opportunity(evidence_ids=("missing",)),))
    with pytest.raises(InvalidLiveContract, match="unknown evidence"):
        _assessment(
            best_next_move=BestNextMove(
                "opportunity-1", "reason", ("missing",), "action", "KPI", ()
            )
        )


def test_market_entity_evidence_must_be_owned_by_that_entity() -> None:
    entity = MarketEntity(
        "competitor-1",
        "Fictional competitor",
        MarketEntityType.COMPETITOR,
        evidence_ids=("evidence-1",),
    )
    owned_by_another = _evidence(owner_entity_id="competitor-2")

    with pytest.raises(InvalidLiveContract, match="does not own"):
        _assessment(market_entities=(entity,), evidence=(owned_by_another,))


def test_market_discovery_result_keeps_entity_evidence_and_limitations_together() -> (
    None
):
    entity = MarketEntity(
        "competitor-1",
        "Fictional competitor",
        MarketEntityType.COMPETITOR,
        evidence_ids=("evidence-1",),
    )
    evidence = _evidence(owner_entity_id="competitor-1")
    result = MarketDiscoveryResult(
        entities=(entity,), evidence=(evidence,), limitations=("Fictional fixture.",)
    )

    assert result.entities == (entity,)
    assert result.evidence == (evidence,)
    assert result.limitations == ("Fictional fixture.",)


def test_market_discovery_result_rejects_unassociated_evidence() -> None:
    entity = MarketEntity(
        "competitor-1",
        "Fictional competitor",
        MarketEntityType.COMPETITOR,
        evidence_ids=("evidence-1",),
    )

    with pytest.raises(InvalidLiveContract, match="does not own"):
        MarketDiscoveryResult(
            entities=(entity,),
            evidence=(_evidence(owner_entity_id="competitor-2"),),
        )


def test_market_position_sample_size_matches_comparable_ids() -> None:
    with pytest.raises(InvalidLiveContract, match="must match"):
        MarketPosition(comparable_competitor_ids=("competitor-1",))

    with pytest.raises(InvalidLiveContract, match="must be unique"):
        MarketPosition(
            comparable_competitor_ids=("competitor-1", "competitor-1"),
            comparison_sample_size=2,
        )


def test_explicit_serialization_produces_readable_json_and_utc_timestamps() -> None:
    evidence = _evidence(
        retrieved_at=datetime.fromisoformat("2026-01-01T12:00:00+00:00")
    )
    assessment = _assessment(evidence=(evidence,))
    result = assessment_to_dict(assessment)
    assert result["business"]["website_url"] is None  # type: ignore[index]
    payload = json.loads(assessment_to_json(assessment))
    assert payload["evidence"][0]["kind"] == "OBSERVED"
    assert payload["evidence"][0]["retrieved_at"] == "2026-01-01T12:00:00+00:00"
    assert payload["best_next_move"]["selected_opportunity_id"] == "opportunity-1"


def test_vertical_profiles_are_declarative_and_lookup_is_case_insensitive() -> None:
    cleaning = vertical_profile_for("house cleaning")
    hvac = vertical_profile_for("HVAC")
    roofing = vertical_profile_for("ROOFING")
    assert cleaning is not None
    assert "property managers" in cleaning.common_customer_categories
    assert "vacation rental managers" in cleaning.partner_categories
    assert "janitorial supply" in cleaning.supplier_categories
    assert hvac is not None and hvac.vertical is Vertical.HVAC
    assert "equipment distributors" in hvac.supplier_categories
    assert roofing is not None and "restoration companies" in roofing.partner_categories
    assert vertical_profile_for("unknown trade") is None


def test_fixture_demo_runs_engine_for_website_and_no_website_businesses() -> None:
    assessment = build_demo_assessment()
    counts = {
        entity_type: sum(
            entity.entity_type is entity_type for entity in assessment.market_entities
        )
        for entity_type in MarketEntityType
    }
    assert counts[MarketEntityType.COMPETITOR] == 3
    assert counts[MarketEntityType.POTENTIAL_CUSTOMER] == 2
    assert counts[MarketEntityType.PARTNER] == 2
    assert counts[MarketEntityType.SUPPLIER] == 2
    assert len(assessment.evidence) >= 6
    assert len(assessment.opportunities) >= 3
    assert assessment.business.website_url is None
    assert any(
        "fictional demonstration data" in item for item in assessment.limitations
    )
    assert all(
        opportunity.opportunity_type is not OpportunityType.WEBSITE_CONVERSION
        for opportunity in assessment.opportunities
    )
    best_next_move = assessment.best_next_move
    assert best_next_move is not None
    assert best_next_move.selected_opportunity_id in {
        opportunity.opportunity_id for opportunity in assessment.opportunities
    }
    rendered = assessment_to_json(assessment)
    assert '"market_entities"' in rendered
    assert '"market_position"' in rendered
    assert '"best_next_move"' in rendered

    hvac_assessment, cleaning_assessment = build_demo_assessments()
    assert hvac_assessment.business.website_url is not None
    assert cleaning_assessment.business.website_url is None
    assert hvac_assessment.opportunities
    assert cleaning_assessment.opportunities
    assert any(
        item.opportunity_type is OpportunityType.WEBSITE_CONVERSION
        for item in hvac_assessment.opportunities
    )


def test_assessment_is_frozen_and_supports_structural_replacement() -> None:
    assessment = _assessment()
    with pytest.raises(FrozenInstanceError):
        assessment.limitations = ("changed",)  # type: ignore[misc]
    updated = replace(assessment, limitations=("known limitation",))
    assert updated.limitations == ("known limitation",)
