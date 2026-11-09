"""Deterministic, evidence-led commercial assessment use case.

Opportunity ranking is an ordinal action-priority heuristic, never a measured
financial impact or revenue estimate:

* impact 4: a missing quote/contact path or owner-reported follow-up gap; 3: an
  observed web or local-visibility issue; 2: an unqualified customer, partner,
  or supplier route;
* evidence strength: OBSERVED=5, REPORTED=4, INFERRED=2, ESTIMATED=1, taking
  the lowest score among the cited records;
* confidence: the lowest supplied confidence rounded up to a 1..5 band, or
  OBSERVED=4, REPORTED=3, INFERRED=2, ESTIMATED=1 when confidence is absent;
* execution and effort are action rubrics: owner-controlled follow-up is 4/2;
  website, profile, prospect qualification, and supplier comparison are 3/2–3;
  a referral arrangement requiring another party is 2/3. No weighted sum is
  used. Ranking is lexicographic: impact, evidence strength, confidence,
  execution, lower effort, then opportunity ID for a stable tie-break.

Urgency, dependencies, financial impact, and time to commercial outcome are
not ranked because LIVE-001A has no evidence-backed fields for them. The
assessment says when those facts are missing instead of estimating them.
"""

from dataclasses import replace
from math import ceil, isfinite
import re

from aeos.live.domain import (
    AssessmentStatus,
    BestNextMove,
    BusinessAssessment,
    BusinessInput,
    DataCoverage,
    EvidenceKind,
    InvalidLiveContract,
    JsonScalar,
    MarketEntity,
    MarketEntityType,
    MarketFinding,
    MarketPosition,
    MarketStructureDimension,
    MarketStructureObservation,
    Opportunity,
    OpportunityType,
    SourceEvidence,
    vertical_profile_for,
)
from aeos.live.ports import (
    MarketDiscoveryResult,
    WebsiteInspectionResult,
    WebsiteSignal,
)

_EVIDENCE_STRENGTH = {
    EvidenceKind.OBSERVED: 5,
    EvidenceKind.REPORTED: 4,
    EvidenceKind.INFERRED: 2,
    EvidenceKind.ESTIMATED: 1,
}
_DEFAULT_CONFIDENCE = {
    EvidenceKind.OBSERVED: 4,
    EvidenceKind.REPORTED: 3,
    EvidenceKind.INFERRED: 2,
    EvidenceKind.ESTIMATED: 1,
}
_ACTION_SCORES: dict[OpportunityType, tuple[int, int, int]] = {
    # impact, execution practicality, effort
    OpportunityType.FOLLOW_UP: (4, 4, 2),
    OpportunityType.WEBSITE_CONVERSION: (3, 3, 3),
    OpportunityType.LOCAL_VISIBILITY: (3, 3, 2),
    OpportunityType.CUSTOMER_ACQUISITION: (2, 3, 3),
    OpportunityType.PARTNERSHIP: (2, 2, 3),
    OpportunityType.SUPPLIER: (2, 3, 3),
}
_MEASUREMENT_KPI = {
    OpportunityType.FOLLOW_UP: "Completed follow-up steps and customer replies recorded for the next review period.",
    OpportunityType.WEBSITE_CONVERSION: "The relevant contact or quote path completes in a manual mobile and desktop check.",
    OpportunityType.LOCAL_VISIBILITY: "Profile status is verified and, if eligible, the public profile URL is recorded.",
    OpportunityType.CUSTOMER_ACQUISITION: "Potential organizations with service fit and a responsible decision-maker verified.",
    OpportunityType.PARTNERSHIP: "A partner discussion is completed and any agreed referral process is recorded.",
    OpportunityType.SUPPLIER: "A like-for-like comparison of product availability and supplier terms is recorded.",
}
_WEBSITE_SIGNAL_LABELS = {
    "quote_request": "a quote request path",
    "quote_request_path": "a quote request path",
    "call_to_action": "a clear next step for customers",
    "contact_information": "visible contact information",
    "service_pages": "pages describing the services offered",
    "mobile_usability": "a usable mobile experience",
    "trust_signals": "customer-facing trust information",
    "local_search_relevance": "service-area information",
}
_CATEGORY_GROUPS = (
    frozenset(
        {
            "property manager",
            "property managers",
            "property management",
            "property management company",
            "property management companies",
        }
    ),
    frozenset(
        {
            "real estate agency",
            "real estate agencies",
            "real estate agent",
            "real estate agents",
        }
    ),
    frozenset({"moving company", "moving companies", "mover", "movers"}),
    frozenset(
        {
            "apartment community",
            "apartment communities",
            "apartment complex",
            "apartment complexes",
        }
    ),
    frozenset(
        {
            "vacation rental manager",
            "vacation rental managers",
            "vacation rental management",
        }
    ),
    frozenset(
        {
            "facility manager",
            "facility managers",
            "facility management",
        }
    ),
    frozenset(
        {
            "general contractor",
            "general contractors",
        }
    ),
)
_REPORTED_INPUT_FIELDS = (
    "service_radius_miles",
    "website_url",
    "google_business_url",
    "monthly_inquiries",
    "monthly_quotes",
    "monthly_jobs",
    "average_job_value",
    "repeat_customer_share",
    "has_structured_follow_up",
)
_US_STATE_CODES = {
    "alabama": "al",
    "alaska": "ak",
    "arizona": "az",
    "arkansas": "ar",
    "california": "ca",
    "colorado": "co",
    "connecticut": "ct",
    "delaware": "de",
    "district of columbia": "dc",
    "florida": "fl",
    "georgia": "ga",
    "hawaii": "hi",
    "idaho": "id",
    "illinois": "il",
    "indiana": "in",
    "iowa": "ia",
    "kansas": "ks",
    "kentucky": "ky",
    "louisiana": "la",
    "maine": "me",
    "maryland": "md",
    "massachusetts": "ma",
    "michigan": "mi",
    "minnesota": "mn",
    "mississippi": "ms",
    "missouri": "mo",
    "montana": "mt",
    "nebraska": "ne",
    "nevada": "nv",
    "new hampshire": "nh",
    "new jersey": "nj",
    "new mexico": "nm",
    "new york": "ny",
    "north carolina": "nc",
    "north dakota": "nd",
    "ohio": "oh",
    "oklahoma": "ok",
    "oregon": "or",
    "pennsylvania": "pa",
    "rhode island": "ri",
    "south carolina": "sc",
    "south dakota": "sd",
    "tennessee": "tn",
    "texas": "tx",
    "utah": "ut",
    "vermont": "vt",
    "virginia": "va",
    "washington": "wa",
    "west virginia": "wv",
    "wisconsin": "wi",
    "wyoming": "wy",
}


def assess_business(
    business: BusinessInput,
    market_discovery: MarketDiscoveryResult,
    *,
    evidence: tuple[SourceEvidence, ...] = (),
    website_inspection: WebsiteInspectionResult | None = None,
) -> BusinessAssessment:
    """Assess supplied business and market facts without performing I/O."""

    if not isinstance(business, BusinessInput):
        raise InvalidLiveContract("business must be a BusinessInput")
    if not isinstance(market_discovery, MarketDiscoveryResult):
        raise InvalidLiveContract("market_discovery must be a MarketDiscoveryResult")
    if not isinstance(evidence, tuple) or any(
        not isinstance(item, SourceEvidence) for item in evidence
    ):
        raise InvalidLiveContract("evidence must be a tuple of SourceEvidence values")

    website_signals, website_evidence = _validate_website_inspection(
        business, website_inspection
    )
    reported_evidence = _reported_business_evidence(business)
    all_evidence = _unique_evidence(
        (
            *market_discovery.evidence,
            *reported_evidence,
            *evidence,
            *website_evidence,
        )
    )
    entities = _associate_owned_evidence(market_discovery.entities, all_evidence)

    evidence_by_id = {item.evidence_id: item for item in all_evidence}
    inferred_evidence: list[SourceEvidence] = []
    validated_fit_ids: dict[str, tuple[str, ...]] = {}
    fit_limitations: list[str] = []
    for entity in entities:
        if entity.entity_type not in {
            MarketEntityType.POTENTIAL_CUSTOMER,
            MarketEntityType.PARTNER,
        }:
            continue
        location_ok, location_status = _entity_location_compatible(
            entity, business, evidence_by_id
        )
        if not location_ok:
            fit_limitations.append(
                _entity_fit_limitation(entity, "local fit", location_status)
            )
            continue

        fit_field = (
            "potential_customer_fit"
            if entity.entity_type is MarketEntityType.POTENTIAL_CUSTOMER
            else "possible_partner_fit"
        )
        explicit_fit, explicit_fit_status = _direct_entity_fit_evidence(
            entity, fit_field, evidence_by_id
        )
        category_evidence, category_status = _entity_field_evidence(
            entity, "category", entity.category, evidence_by_id
        )
        profile = vertical_profile_for(business.industry)
        if explicit_fit:
            validated_fit_ids[entity.entity_id] = tuple(
                item.evidence_id for item in explicit_fit
            )
            continue
        if explicit_fit_status in {"conflicting", "value_mismatch"}:
            fit_limitations.append(
                f"{entity.name} was not promoted because direct {fit_field} evidence is negative or conflicting."
            )
            continue
        if profile is None:
            fit_limitations.append(
                f"{entity.name} was not promoted as a commercial fit: {business.industry} has no declared vertical profile, and no direct {fit_field} evidence supports this specific fit."
            )
            continue
        if category_status != "supported":
            fit_limitations.append(
                _entity_fit_limitation(entity, "category fit", category_status)
            )
            if explicit_fit_status == "conflicting":
                fit_limitations.append(
                    f"{entity.name} has conflicting direct {fit_field} evidence; no commercial fit was promoted."
                )
            continue
        if not _category_is_relevant(entity.category, business, entity.entity_type):
            fit_limitations.append(
                f"{entity.name} was not promoted as a commercial fit because its supported category does not match the declared {business.industry} profile."
            )
            continue
        field = fit_field
        role = (
            "a possible customer segment"
            if entity.entity_type is MarketEntityType.POTENTIAL_CUSTOMER
            else "a possible referral partner"
        )
        evidence_id = f"aeos-inference:{field}:{entity.entity_id}"
        fit_evidence = SourceEvidence(
            evidence_id=evidence_id,
            kind=EvidenceKind.INFERRED,
            subject=entity.name,
            field=field,
            value=f"{entity.category} may fit {business.industry} as {role}.",
            source_name="AEOS deterministic category-fit rule",
            excerpt=(
                "Category compatibility suggests a route to investigate; it does not establish need, authority, intent, or an existing relationship."
            ),
            assumptions=(
                f"The business operates in {business.industry}.",
                f"The discovered entity is categorized as {entity.category}.",
                "No purchasing need or relationship was verified.",
            ),
            owner_entity_id=entity.entity_id,
        )
        inferred_evidence.append(fit_evidence)
        validated_fit_ids[entity.entity_id] = (evidence_id,)

    supplier_fit_limitations: list[str] = []
    for entity in entities:
        if entity.entity_type is not MarketEntityType.SUPPLIER:
            continue
        supplier_ok, supplier_status = _supplier_entity_supported(
            entity, business, evidence_by_id
        )
        if not supplier_ok:
            supplier_fit_limitations.append(
                _entity_fit_limitation(entity, "supplier fit", supplier_status)
            )

    all_evidence = _unique_evidence((*all_evidence, *inferred_evidence))
    evidence_by_id = {item.evidence_id: item for item in all_evidence}
    entities = tuple(
        replace(
            entity,
            evidence_ids=tuple(
                sorted(
                    set(entity.evidence_ids)
                    | (
                        set(validated_fit_ids[entity.entity_id])
                        if entity.entity_id in validated_fit_ids
                        else set()
                    )
                )
            ),
        )
        for entity in entities
    )
    target_evidence = tuple(
        item
        for item in all_evidence
        if item.owner_entity_id is None
        and item.subject.casefold() == business.business_name.casefold()
    )

    limitations = list(market_discovery.limitations)
    limitations.extend(fit_limitations)
    limitations.extend(supplier_fit_limitations)
    opportunities = _identify_opportunities(
        business,
        entities,
        target_evidence,
        website_signals,
        website_inspection,
        evidence_by_id,
        validated_fit_ids,
        limitations,
    )
    market_position = _benchmark(
        business, entities, target_evidence, evidence_by_id, website_inspection
    )
    limitations.extend(market_position.limitations)
    market_observations = _market_observations(entities, evidence_by_id, business)
    limitations.extend(
        _general_limitations(business, target_evidence, website_inspection)
    )
    limitations = list(dict.fromkeys(limitations))

    ranked_opportunities = rank_opportunities(tuple(opportunities))
    status = (
        AssessmentStatus.READY
        if ranked_opportunities
        else AssessmentStatus.INSUFFICIENT_DATA
    )
    best_next_move = (
        _best_next_move(ranked_opportunities) if ranked_opportunities else None
    )
    if status is AssessmentStatus.INSUFFICIENT_DATA:
        limitations.append(
            "The supplied evidence does not support a defensible commercial action yet."
        )
        limitations = list(dict.fromkeys(limitations))

    return BusinessAssessment(
        business=business,
        evidence=all_evidence,
        market_entities=entities,
        market_position=market_position,
        market_structure_observations=market_observations,
        opportunities=ranked_opportunities,
        best_next_move=best_next_move,
        limitations=tuple(limitations),
        status=status,
    )


def rank_opportunities(
    opportunities: tuple[Opportunity, ...],
) -> tuple[Opportunity, ...]:
    """Rank by ordinal action priority, then a stable opportunity-ID tie-break.

    The order is impact rubric, evidence strength, confidence, executability,
    lower effort, then ID. The dimensions are ordinal heuristics, not financial
    measurements.
    """

    if not isinstance(opportunities, tuple) or any(
        not isinstance(item, Opportunity) for item in opportunities
    ):
        raise InvalidLiveContract("opportunities must be a tuple of Opportunity values")
    if len({item.opportunity_id for item in opportunities}) != len(opportunities):
        raise InvalidLiveContract("opportunity identifiers must be unique")
    return tuple(
        sorted(
            opportunities,
            key=lambda item: (
                -item.impact,
                -item.evidence_strength,
                -item.confidence,
                -item.executability,
                item.effort,
                item.opportunity_id.casefold(),
                item.opportunity_id,
            ),
        )
    )


def render_assessment_summary(assessment: BusinessAssessment) -> str:
    """Render a deterministic, plain-language summary from LIVE contracts."""

    if not isinstance(assessment, BusinessAssessment):
        raise InvalidLiveContract("assessment must be a BusinessAssessment")
    business = assessment.business
    lines = [
        f"Business: {business.business_name}",
        f"Industry and area: {business.industry} — {business.city}, {business.state}",
        f"Assessment status: {assessment.status.value}",
        "",
        "What the evidence shows:",
    ]
    if assessment.market_position.comparable_competitor_ids:
        lines.append(
            "- The supplied discovery sample contains "
            f"{assessment.market_position.comparison_sample_size} location- and category-matched competitors; it is not a market-share estimate."
        )
    else:
        lines.append(
            "- No competitor listing with evidence-matched category and location was available for comparison."
        )
    for finding in (
        *assessment.market_position.relative_strengths,
        *assessment.market_position.relative_weaknesses,
        *assessment.market_position.market_gaps,
    ):
        lines.append(f"- {finding.label}: {finding.description}")
    for observation in assessment.market_structure_observations:
        lines.append(f"- {observation.description}")

    evidence_by_id = {item.evidence_id: item for item in assessment.evidence}
    promoted_fit_ids: set[str] = set()
    for entity in assessment.market_entities:
        if entity.entity_type not in {
            MarketEntityType.POTENTIAL_CUSTOMER,
            MarketEntityType.PARTNER,
        }:
            continue
        fit_field = (
            "potential_customer_fit"
            if entity.entity_type is MarketEntityType.POTENTIAL_CUSTOMER
            else "possible_partner_fit"
        )
        direct_fit, direct_fit_status = _direct_entity_fit_evidence(
            entity, fit_field, evidence_by_id
        )
        location_ok, _ = _entity_location_compatible(entity, business, evidence_by_id)
        category_evidence, category_status = _entity_field_evidence(
            entity, "category", entity.category, evidence_by_id
        )
        profile = vertical_profile_for(business.industry)
        if not location_ok:
            continue
        if direct_fit:
            promoted_fit_ids.add(entity.entity_id)
        elif direct_fit_status not in {"conflicting", "value_mismatch"} and (
            category_evidence
            and category_status == "supported"
            and profile is not None
            and _category_is_relevant(entity.category, business, entity.entity_type)
        ):
            promoted_fit_ids.add(entity.entity_id)

    for entity_type, label in (
        (
            MarketEntityType.POTENTIAL_CUSTOMER,
            "Potential prospects (not qualified leads)",
        ),
        (
            MarketEntityType.PARTNER,
            "Possible referral partners (no relationship verified)",
        ),
        (MarketEntityType.SUPPLIER, "Supplier listings (terms not compared)"),
    ):
        names = sorted(
            entity.name
            for entity in assessment.market_entities
            if entity.entity_type is entity_type
            and (
                entity.entity_id in promoted_fit_ids
                if entity_type
                in {MarketEntityType.POTENTIAL_CUSTOMER, MarketEntityType.PARTNER}
                else True
            )
        )
        if names:
            lines.append(f"- {label}: {', '.join(names)}.")
    unpromoted_names = sorted(
        entity.name
        for entity in assessment.market_entities
        if entity.entity_type
        in {MarketEntityType.POTENTIAL_CUSTOMER, MarketEntityType.PARTNER}
        and entity.entity_id not in promoted_fit_ids
    )
    if unpromoted_names:
        lines.append(
            "- Other discovered organizations (commercial fit not established): "
            + ", ".join(unpromoted_names)
            + "."
        )

    website_status = _coverage_note(assessment, "website_status")
    if website_status:
        lines.append(f"- Website: {website_status}")
    profile_status = _coverage_note(assessment, "google_business_profile_status")
    if profile_status:
        lines.append(f"- Google Business Profile: {profile_status}")

    lines.extend(("", "Commercial opportunities:"))
    if assessment.opportunities:
        for opportunity in assessment.opportunities:
            lines.append(f"- {opportunity.title}: {opportunity.description}")
    else:
        lines.append(
            "- There is not enough evidence to recommend a commercial action yet."
        )

    if assessment.best_next_move is not None:
        move = assessment.best_next_move
        lines.extend(
            (
                "",
                f"Best next action: {move.first_action}",
                f"Why this action: {move.why_this_one}",
                f"How to check progress: {move.measurement_kpi}",
            )
        )

    lines.extend(("", "Evidence supplied (not every record supports a finding):"))
    for item in assessment.evidence:
        value = _display_value(item.value)
        lines.append(
            f"- [{item.kind.value}] {item.evidence_id}: {item.subject} — {item.field} = {value} (source: {item.source_name})."
        )
    lines.extend(("", "What remains unknown:"))
    if assessment.limitations:
        lines.extend(f"- {item}" for item in assessment.limitations)
    else:
        lines.append("- No additional limitation was recorded.")
    lines.extend(("", "Useful next information to collect:"))
    next_information = _next_information_to_collect(assessment)
    lines.extend(f"- {item}" for item in next_information)
    return "\n".join(lines)


def _reported_business_evidence(business: BusinessInput) -> tuple[SourceEvidence, ...]:
    rows: list[SourceEvidence] = []
    for field in _REPORTED_INPUT_FIELDS:
        value = getattr(business, field)
        if value is None:
            continue
        rows.append(
            SourceEvidence(
                evidence_id=f"reported:business:{field}",
                kind=EvidenceKind.REPORTED,
                subject=business.business_name,
                field=field,
                value=value,
                source_name="Business-provided input",
            )
        )
    if business.main_customer_sources is not None:
        for index, source in enumerate(business.main_customer_sources):
            rows.append(
                SourceEvidence(
                    evidence_id=f"reported:business:main_customer_sources:{index}",
                    kind=EvidenceKind.REPORTED,
                    subject=business.business_name,
                    field="main_customer_sources",
                    value=source,
                    source_name="Business-provided input",
                )
            )
    return tuple(rows)


def _validate_website_inspection(
    business: BusinessInput,
    inspection: WebsiteInspectionResult | None,
) -> tuple[tuple[WebsiteSignal, ...], tuple[SourceEvidence, ...]]:
    if inspection is None:
        return (), ()
    if not isinstance(inspection, WebsiteInspectionResult):
        raise InvalidLiveContract(
            "website_inspection must be a WebsiteInspectionResult or None"
        )
    if not isinstance(inspection.signals, tuple) or any(
        not isinstance(item, WebsiteSignal) for item in inspection.signals
    ):
        raise InvalidLiveContract(
            "website signals must be a tuple of WebsiteSignal values"
        )
    evidence = inspection.evidence
    if not isinstance(evidence, tuple) or any(
        not isinstance(item, SourceEvidence) for item in evidence
    ):
        raise InvalidLiveContract(
            "website evidence must be a tuple of SourceEvidence values"
        )
    evidence_by_id = {item.evidence_id: item for item in evidence}
    if len(evidence_by_id) != len(evidence):
        raise InvalidLiveContract("website evidence identifiers must be unique")
    for source in evidence:
        if not _subject_matches(source.subject, business.business_name):
            raise InvalidLiveContract(
                "website inspection evidence subject must match the assessed business"
            )
        if source.source_url is not None and business.website_url is not None:
            if _normalize_url(source.source_url) != _normalize_url(
                business.website_url
            ):
                raise InvalidLiveContract(
                    "website inspection evidence URL must match the business website URL"
                )
    seen_fields: set[str] = set()
    for signal in inspection.signals:
        if not isinstance(signal.field, str) or not signal.field.strip():
            raise InvalidLiveContract("website signal field must be non-blank")
        if not isinstance(signal.evidence_id, str) or not signal.evidence_id.strip():
            raise InvalidLiveContract("website signal evidence_id must be non-blank")
        if signal.field in seen_fields:
            raise InvalidLiveContract(
                "website signal fields must not conflict or repeat"
            )
        seen_fields.add(signal.field)
        value = signal.value
        if value is not None and type(value) not in (str, int, float, bool):
            raise InvalidLiveContract("website signal value must be a JSON scalar")
        if type(value) is float and not isfinite(value):
            raise InvalidLiveContract("website signal value must be finite")
        matching_source = evidence_by_id.get(signal.evidence_id)
        if matching_source is None:
            raise InvalidLiveContract(
                f"website signal {signal.field} references missing evidence"
            )
        if matching_source.kind is not EvidenceKind.OBSERVED:
            raise InvalidLiveContract(
                f"website signal {signal.field} must cite OBSERVED evidence"
            )
        if matching_source.field != signal.field or not _same_scalar(
            matching_source.value, value
        ):
            raise InvalidLiveContract(
                f"website signal {signal.field} conflicts with its source evidence"
            )
        if matching_source.owner_entity_id is not None:
            raise InvalidLiveContract(
                "website inspection evidence cannot be owned by a market entity"
            )
    if any(item.owner_entity_id is not None for item in evidence):
        raise InvalidLiveContract(
            "website inspection evidence cannot be owned by a market entity"
        )
    return inspection.signals, evidence


def _unique_evidence(
    evidence: tuple[SourceEvidence, ...],
) -> tuple[SourceEvidence, ...]:
    by_id: dict[str, SourceEvidence] = {}
    for item in evidence:
        if item.evidence_id in by_id:
            raise InvalidLiveContract(
                f"duplicate evidence identifier: {item.evidence_id}"
            )
        by_id[item.evidence_id] = item
    return evidence


def _associate_owned_evidence(
    entities: tuple[MarketEntity, ...], evidence: tuple[SourceEvidence, ...]
) -> tuple[MarketEntity, ...]:
    entity_ids = {entity.entity_id for entity in entities}
    owned_ids: dict[str, list[str]] = {entity_id: [] for entity_id in entity_ids}
    for item in evidence:
        if item.owner_entity_id is None:
            continue
        if item.owner_entity_id not in entity_ids:
            raise InvalidLiveContract(
                f"evidence {item.evidence_id} references an unknown owner entity"
            )
        owned_ids[item.owner_entity_id].append(item.evidence_id)
    return tuple(
        replace(
            entity,
            evidence_ids=tuple(
                sorted(set(entity.evidence_ids) | set(owned_ids[entity.entity_id]))
            ),
        )
        for entity in entities
    )


def _entity_field_evidence(
    entity: MarketEntity,
    field: str,
    value: JsonScalar,
    evidence_by_id: dict[str, SourceEvidence],
) -> tuple[tuple[SourceEvidence, ...], str]:
    """Return direct evidence only when it supports this entity attribute."""

    rows = tuple(
        evidence_by_id[evidence_id]
        for evidence_id in entity.evidence_ids
        if evidence_id in evidence_by_id
        and evidence_by_id[evidence_id].owner_entity_id == entity.entity_id
        and evidence_by_id[evidence_id].field == field
    )
    if not rows:
        return (), "missing"
    subject_rows = tuple(
        item for item in rows if _subject_matches(item.subject, entity.name)
    )
    if not subject_rows:
        return (), "subject_mismatch"
    direct_rows = tuple(
        item
        for item in subject_rows
        if item.kind in {EvidenceKind.OBSERVED, EvidenceKind.REPORTED}
    )
    if not direct_rows:
        return (), "inappropriate_kind"
    values = {_entity_value_key(field, item.value) for item in direct_rows}
    if len(values) > 1:
        return (), "conflicting"
    if _entity_value_key(field, value) not in values:
        return (), "value_mismatch"
    return direct_rows, "supported"


def _direct_entity_fit_evidence(
    entity: MarketEntity,
    field: str,
    evidence_by_id: dict[str, SourceEvidence],
) -> tuple[tuple[SourceEvidence, ...], str]:
    rows = tuple(
        evidence_by_id[evidence_id]
        for evidence_id in entity.evidence_ids
        if evidence_id in evidence_by_id
        and evidence_by_id[evidence_id].owner_entity_id == entity.entity_id
        and evidence_by_id[evidence_id].field == field
        and _subject_matches(evidence_by_id[evidence_id].subject, entity.name)
    )
    if not rows:
        return (), "missing"
    direct_rows = tuple(
        item
        for item in rows
        if item.kind in {EvidenceKind.OBSERVED, EvidenceKind.REPORTED}
    )
    if not direct_rows:
        return (), "inappropriate_kind"
    values = {(type(item.value), item.value) for item in direct_rows}
    if len(values) > 1:
        return (), "conflicting"
    if values != {(bool, True)}:
        return (), "value_mismatch"
    return direct_rows, "supported"


def _entity_fit_limitation(entity: MarketEntity, claim: str, status: str) -> str:
    explanations = {
        "missing": "field-matched source evidence is missing",
        "subject_mismatch": "source evidence is not associated with this entity name",
        "inappropriate_kind": "only inferred or estimated evidence supports the field",
        "conflicting": "field-matched source evidence conflicts",
        "value_mismatch": "the source value does not match the entity attribute",
        "state_mismatch": "the supported state does not match the business state",
        "city_mismatch": "the supported city is outside the business city and no verified in-radius distance applies",
        "distance_mismatch": "the supported distance exceeds the business service radius",
        "unsupported_vertical": "the industry has no declared vertical profile",
        "category_not_relevant": "the supported category is not listed for this vertical",
        "fit_evidence_missing": "no direct evidence supports this specific supplier fit",
    }
    detail = explanations.get(status, status.replace("_", " "))
    return f"{entity.name} was not promoted for {claim}: {detail}."


def _entity_value_key(field: str, value: JsonScalar) -> tuple[type[object], object]:
    if type(value) is str:
        if field == "category":
            return str, _canonical_category(value)
        if field == "city":
            return str, _normalize_text(value)
        if field == "state":
            return str, _normalize_state(value)
        if field == "services":
            return str, _normalize_text(value)
    if field == "distance_miles":
        if type(value) is int:
            return float, float(value)
        if type(value) is float:
            return float, value
    return type(value), value


def _subject_matches(subject: str, expected: str) -> bool:
    return _normalize_text(subject) == _normalize_text(expected)


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").casefold()


def _entity_location_compatible(
    entity: MarketEntity,
    business: BusinessInput,
    evidence_by_id: dict[str, SourceEvidence],
) -> tuple[bool, str]:
    _, state_status = _entity_field_evidence(
        entity, "state", entity.state, evidence_by_id
    )
    if state_status != "supported":
        return False, state_status
    if entity.state is None or _normalize_state(entity.state) != _normalize_state(
        business.state
    ):
        return False, "state_mismatch"
    if business.service_radius_miles is not None and entity.distance_miles is not None:
        _, distance_status = _entity_field_evidence(
            entity, "distance_miles", entity.distance_miles, evidence_by_id
        )
        if distance_status == "supported":
            return (
                entity.distance_miles <= business.service_radius_miles,
                "supported"
                if entity.distance_miles <= business.service_radius_miles
                else "distance_mismatch",
            )
    _, city_status = _entity_field_evidence(entity, "city", entity.city, evidence_by_id)
    if city_status != "supported":
        return False, city_status
    if entity.city is None or _normalize_text(entity.city) != _normalize_text(
        business.city
    ):
        return False, "city_mismatch"
    return True, "supported"


def _category_is_relevant(
    category: str | None,
    business: BusinessInput,
    entity_type: MarketEntityType,
) -> bool:
    if category is None:
        return False
    profile = vertical_profile_for(business.industry)
    if profile is None:
        return False
    normalized_category = _canonical_category(category)
    relevant_categories = (
        profile.common_customer_categories
        if entity_type is MarketEntityType.POTENTIAL_CUSTOMER
        else profile.partner_categories
    )
    allowed = {_canonical_category(item) for item in relevant_categories}
    return normalized_category in allowed


def _supplier_is_relevant(entity: MarketEntity, business: BusinessInput) -> bool:
    if entity.category is None:
        return False
    profile = vertical_profile_for(business.industry)
    if profile is None:
        return False
    allowed = {_canonical_category(item) for item in profile.supplier_categories}
    return _canonical_category(entity.category) in allowed


def _supplier_entity_supported(
    entity: MarketEntity,
    business: BusinessInput,
    evidence_by_id: dict[str, SourceEvidence],
) -> tuple[bool, str]:
    location_ok, location_status = _entity_location_compatible(
        entity, business, evidence_by_id
    )
    if not location_ok:
        return False, location_status
    explicit_fit, explicit_status = _direct_entity_fit_evidence(
        entity, "supplier_fit", evidence_by_id
    )
    if explicit_fit:
        return True, "supported"
    profile = vertical_profile_for(business.industry)
    if profile is None:
        return False, "unsupported_vertical"
    _, category_status = _entity_field_evidence(
        entity, "category", entity.category, evidence_by_id
    )
    if category_status != "supported":
        return False, category_status
    if not _supplier_is_relevant(entity, business):
        return False, "category_not_relevant"
    if explicit_status == "conflicting":
        return False, "conflicting"
    if explicit_status == "value_mismatch":
        return False, "fit_evidence_missing"
    return True, "supported"


def _canonical_category(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    for group in _CATEGORY_GROUPS:
        if normalized in group:
            return sorted(group)[0]
    for suffix in (" services", " service", " company", " companies", " contractor"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)].strip()
    return normalized


def _fit_support_evidence_ids(
    entity: MarketEntity,
    business: BusinessInput,
    fit_evidence_ids: tuple[str, ...],
    evidence_by_id: dict[str, SourceEvidence],
) -> tuple[str, ...]:
    """Cite only fit and location fields used to promote this entity."""

    support_ids = set(_entity_location_evidence_ids(entity, business, evidence_by_id))
    support_ids.update(fit_evidence_ids)
    if any(
        evidence_by_id[evidence_id].kind is EvidenceKind.INFERRED
        for evidence_id in fit_evidence_ids
    ):
        category_rows, _ = _entity_field_evidence(
            entity, "category", entity.category, evidence_by_id
        )
        support_ids.update(item.evidence_id for item in category_rows)
    return tuple(sorted(support_ids))


def _entity_location_evidence_ids(
    entity: MarketEntity,
    business: BusinessInput,
    evidence_by_id: dict[str, SourceEvidence],
) -> tuple[str, ...]:
    support_ids: set[str] = set()
    state_rows, _ = _entity_field_evidence(
        entity, "state", entity.state, evidence_by_id
    )
    support_ids.update(item.evidence_id for item in state_rows)
    distance_rows: tuple[SourceEvidence, ...] = ()
    distance_status = "missing"
    if business.service_radius_miles is not None and entity.distance_miles is not None:
        distance_rows, distance_status = _entity_field_evidence(
            entity, "distance_miles", entity.distance_miles, evidence_by_id
        )
    if distance_status == "supported":
        support_ids.update(item.evidence_id for item in distance_rows)
    else:
        city_rows, _ = _entity_field_evidence(
            entity, "city", entity.city, evidence_by_id
        )
        support_ids.update(item.evidence_id for item in city_rows)
    return tuple(sorted(support_ids))


def _entity_listing_evidence_ids(
    entity: MarketEntity,
    business: BusinessInput,
    evidence_by_id: dict[str, SourceEvidence],
) -> tuple[str, ...]:
    category_rows, _ = _entity_field_evidence(
        entity, "category", entity.category, evidence_by_id
    )
    support_ids = {
        *(item.evidence_id for item in category_rows),
        *_entity_location_evidence_ids(entity, business, evidence_by_id),
    }
    if entity.entity_type is MarketEntityType.SUPPLIER:
        fit_rows, _ = _direct_entity_fit_evidence(
            entity, "supplier_fit", evidence_by_id
        )
        support_ids.update(item.evidence_id for item in fit_rows)
    return tuple(sorted(support_ids))


def _identify_opportunities(
    business: BusinessInput,
    entities: tuple[MarketEntity, ...],
    target_evidence: tuple[SourceEvidence, ...],
    website_signals: tuple[WebsiteSignal, ...],
    website_inspection: WebsiteInspectionResult | None,
    evidence_by_id: dict[str, SourceEvidence],
    validated_fit_ids: dict[str, tuple[str, ...]],
    limitations: list[str],
) -> list[Opportunity]:
    opportunities: list[Opportunity] = []
    follow_up = _consistent_field_records(target_evidence, "has_structured_follow_up")
    if follow_up is None or not follow_up:
        limitations.append(
            "Follow-up practices were not assessed because owner-provided or observed evidence is missing or contradictory."
        )
    elif follow_up and all(
        item.value is False
        and item.kind in {EvidenceKind.REPORTED, EvidenceKind.OBSERVED}
        for item in follow_up
    ):
        opportunities.append(
            _make_opportunity(
                opportunity_id="follow-up-process",
                opportunity_type=OpportunityType.FOLLOW_UP,
                title="Create a simple quote follow-up routine",
                description=(
                    "The supplied evidence says there is no structured follow-up. No lost sales or revenue can be calculated from that fact alone."
                ),
                evidence_ids=tuple(item.evidence_id for item in follow_up),
                evidence_by_id=evidence_by_id,
                recommended_action=(
                    "Review recent quotes, choose one appropriate follow-up step, and record whether it was completed and whether the customer replied."
                ),
            )
        )
    elif follow_up:
        limitations.append(
            "Available follow-up evidence does not confirm that a follow-up process is absent, so no follow-up weakness was inferred."
        )

    profile_status = _consistent_field_records(
        target_evidence, "google_business_profile_present"
    )
    if profile_status is None:
        limitations.append(
            "Google Business Profile presence has conflicting source values; no create-or-claim recommendation was made."
        )
    elif profile_status:
        status_values = {item.value for item in profile_status}
        if business.google_business_url is not None and status_values == {False}:
            limitations.append(
                "The supplied Google Business Profile URL conflicts with evidence reporting no profile; the status must be reconciled before acting."
            )
        elif len(status_values) > 1:
            limitations.append(
                "Google Business Profile presence has conflicting source values; no create-or-claim recommendation was made."
            )
        elif profile_status[0].value is False:
            direct_status = tuple(
                item
                for item in profile_status
                if item.kind in {EvidenceKind.OBSERVED, EvidenceKind.REPORTED}
            )
            if direct_status:
                observed_absence = any(
                    item.kind is EvidenceKind.OBSERVED for item in direct_status
                )
                action = (
                    "Confirm eligibility, then create or claim the business profile if the observed absence still holds."
                    if observed_absence
                    else "First verify whether a profile already exists; the current absence report came from the business owner."
                )
                opportunities.append(
                    _make_opportunity(
                        opportunity_id="local-profile-presence",
                        opportunity_type=OpportunityType.LOCAL_VISIBILITY,
                        title="Verify local profile visibility",
                        description=(
                            "A source explicitly reports no Google Business Profile. The source type determines whether this is observed or owner-reported; no other listing absence is assumed."
                        ),
                        evidence_ids=tuple(item.evidence_id for item in direct_status),
                        evidence_by_id=evidence_by_id,
                        recommended_action=action,
                    )
                )
    elif business.google_business_url is None:
        limitations.append(
            "Google Business Profile status was not supplied or inspected; a missing URL does not confirm that no profile exists."
        )
    negative_signals = tuple(
        signal
        for signal in website_signals
        if signal.field in _WEBSITE_SIGNAL_LABELS
        and (
            signal.value is False
            or (type(signal.value) is str and not signal.value.strip())
        )
    )
    if negative_signals:
        evidence_ids = tuple(signal.evidence_id for signal in negative_signals)
        missing_labels = tuple(
            dict.fromkeys(
                _WEBSITE_SIGNAL_LABELS[item.field] for item in negative_signals
            )
        )
        opportunities.append(
            _make_opportunity(
                opportunity_id="website-conversion-friction",
                opportunity_type=OpportunityType.WEBSITE_CONVERSION,
                title="Make it easier for customers to take the next step",
                description=(
                    "The inspected page did not show "
                    + ", ".join(missing_labels)
                    + ". This finding applies only to the inspected page and signals."
                ),
                evidence_ids=evidence_ids,
                evidence_by_id=evidence_by_id,
                impact_override=(
                    4
                    if any(
                        item.field
                        in {
                            "quote_request",
                            "quote_request_path",
                            "call_to_action",
                            "contact_information",
                        }
                        for item in negative_signals
                    )
                    else 3
                ),
                recommended_action=(
                    "Add or repair the missing customer action(s), then manually test the path on a phone and desktop."
                ),
            )
        )
    elif not website_signals:
        limitations.append(
            "Website content and conversion paths were not inspected; no website weakness was inferred."
            if not website_inspection
            else "A website inspection result was supplied without structured signals; no conversion finding was inferred."
        )

    fit_by_type = {
        entity_type: tuple(
            sorted(
                (item for item in entities if item.entity_type is entity_type),
                key=lambda item: item.entity_id,
            )
        )
        for entity_type in (
            MarketEntityType.POTENTIAL_CUSTOMER,
            MarketEntityType.PARTNER,
        )
    }
    customer_entities = tuple(
        item
        for item in fit_by_type[MarketEntityType.POTENTIAL_CUSTOMER]
        if item.entity_id in validated_fit_ids
    )
    if customer_entities:
        evidence_ids = tuple(
            evidence_id
            for entity in customer_entities
            for evidence_id in _fit_support_evidence_ids(
                entity,
                business,
                validated_fit_ids[entity.entity_id],
                evidence_by_id,
            )
        )
        names = ", ".join(item.name for item in customer_entities)
        opportunities.append(
            _make_opportunity(
                opportunity_id="qualify-local-prospects",
                opportunity_type=OpportunityType.CUSTOMER_ACQUISITION,
                title="Qualify potential local customers",
                description=(
                    f"Discovery identified {names} in a relevant business category. This is a potential fit only: service need, decision-maker, and buying intent are not verified."
                ),
                evidence_ids=evidence_ids,
                evidence_by_id=evidence_by_id,
                recommended_action=(
                    "Check service-area fit and identify whether each organization coordinates this kind of work before deciding whether to contact it."
                ),
            )
        )

    partner_entities = tuple(
        item
        for item in fit_by_type[MarketEntityType.PARTNER]
        if item.entity_id in validated_fit_ids
    )
    if partner_entities:
        evidence_ids = tuple(
            evidence_id
            for entity in partner_entities
            for evidence_id in _fit_support_evidence_ids(
                entity,
                business,
                validated_fit_ids[entity.entity_id],
                evidence_by_id,
            )
        )
        names = ", ".join(item.name for item in partner_entities)
        opportunities.append(
            _make_opportunity(
                opportunity_id="explore-referral-partners",
                opportunity_type=OpportunityType.PARTNERSHIP,
                title="Explore a relevant local referral relationship",
                description=(
                    f"Discovery identified {names} in a potentially complementary category. No referral arrangement or customer overlap is established."
                ),
                evidence_ids=evidence_ids,
                evidence_by_id=evidence_by_id,
                recommended_action=(
                    "Choose one organization, verify that customer needs overlap, and ask whether a mutual referral arrangement would be useful."
                ),
            )
        )

    supplier_entities = tuple(
        sorted(
            (
                item
                for item in entities
                if item.entity_type is MarketEntityType.SUPPLIER
                and _supplier_entity_supported(item, business, evidence_by_id)[0]
            ),
            key=lambda item: item.entity_id,
        )
    )
    if len(supplier_entities) >= 2:
        evidence_ids = tuple(
            evidence_id
            for entity in supplier_entities
            for evidence_id in _entity_listing_evidence_ids(
                entity, business, evidence_by_id
            )
        )
        names = ", ".join(item.name for item in supplier_entities)
        opportunities.append(
            _make_opportunity(
                opportunity_id="compare-supplier-options",
                opportunity_type=OpportunityType.SUPPLIER,
                title="Compare listed supplier options",
                description=(
                    f"Discovery returned supplier listings for {names}. Product overlap, current supplier dependence, prices, and delivery terms were not verified."
                ),
                evidence_ids=evidence_ids,
                evidence_by_id=evidence_by_id,
                recommended_action=(
                    "Compare the same frequently purchased items, availability, delivery, and terms with the listed suppliers before changing a vendor."
                ),
            )
        )
    elif supplier_entities:
        limitations.append(
            "Only one supplier listing was supported by direct evidence; supplier alternatives and dependency cannot be assessed."
        )
    return opportunities


def _consistent_field_records(
    evidence: tuple[SourceEvidence, ...], field: str
) -> tuple[SourceEvidence, ...] | None:
    rows = tuple(
        item
        for item in evidence
        if item.field == field and item.owner_entity_id is None
    )
    values = {(type(item.value), repr(item.value)) for item in rows}
    if len(values) > 1:
        return None
    return rows


def _make_opportunity(
    *,
    opportunity_id: str,
    opportunity_type: OpportunityType,
    title: str,
    description: str,
    evidence_ids: tuple[str, ...],
    evidence_by_id: dict[str, SourceEvidence],
    impact_override: int | None = None,
    recommended_action: str,
) -> Opportunity:
    ids = tuple(sorted(set(evidence_ids)))
    if not ids:
        raise InvalidLiveContract("an opportunity requires supporting evidence")
    sources = tuple(evidence_by_id[item] for item in ids)
    impact, executability, effort = _ACTION_SCORES[opportunity_type]
    if impact_override is not None:
        impact = impact_override
    evidence_strength = min(_EVIDENCE_STRENGTH[item.kind] for item in sources)
    confidence = min(_confidence_score(item) for item in sources)
    return Opportunity(
        opportunity_id=opportunity_id,
        opportunity_type=opportunity_type,
        title=title,
        description=description,
        evidence_ids=ids,
        impact=impact,
        confidence=confidence,
        evidence_strength=evidence_strength,
        executability=executability,
        effort=effort,
        time_to_value="First action can begin now; outcome timing is unknown.",
        recommended_action=recommended_action,
    )


def _confidence_score(evidence: SourceEvidence) -> int:
    if evidence.confidence is None:
        return _DEFAULT_CONFIDENCE[evidence.kind]
    return max(1, min(5, ceil(evidence.confidence * 5)))


def _best_next_move(ranked_opportunities: tuple[Opportunity, ...]) -> BestNextMove:
    opportunity = ranked_opportunities[0]
    components = (
        f"impact={opportunity.impact}, evidence_strength={opportunity.evidence_strength}, "
        f"confidence={opportunity.confidence}, executability={opportunity.executability}, "
        f"effort={opportunity.effort}"
    )
    reason = (
        "Ordinal action-priority heuristic (rubric values, not measured financial impact). "
        f"Selected score components: {components}."
    )
    if len(ranked_opportunities) == 1:
        reason += " This is the only opportunity supported by the supplied evidence."
    else:
        runner_up = ranked_opportunities[1]
        reason += (
            f" Compared with second-ranked '{runner_up.title}' "
            f"({_priority_component_text(runner_up)}), "
            f"it ranks first because {_first_priority_difference(opportunity, runner_up)}."
        )
    return BestNextMove(
        selected_opportunity_id=opportunity.opportunity_id,
        why_this_one=reason,
        evidence_ids=opportunity.evidence_ids,
        first_action=opportunity.recommended_action,
        measurement_kpi=_MEASUREMENT_KPI[opportunity.opportunity_type],
        limitations=(
            "Impact and confidence are ordinal rubric values, not revenue forecasts.",
            "Urgency, dependencies, and outcome timing were not ranked because the available contracts contain no verified values for them.",
        ),
        ready_to_use_asset=opportunity.ready_to_use_asset,
    )


def _priority_component_text(opportunity: Opportunity) -> str:
    return (
        f"impact={opportunity.impact}, "
        f"evidence_strength={opportunity.evidence_strength}, "
        f"confidence={opportunity.confidence}, "
        f"executability={opportunity.executability}, effort={opportunity.effort}"
    )


def _first_priority_difference(first: Opportunity, second: Opportunity) -> str:
    comparisons = (
        ("impact", first.impact, second.impact, "higher"),
        (
            "evidence strength",
            first.evidence_strength,
            second.evidence_strength,
            "higher",
        ),
        ("confidence", first.confidence, second.confidence, "higher"),
        ("executability", first.executability, second.executability, "higher"),
        ("effort", first.effort, second.effort, "lower"),
    )
    for label, first_value, second_value, preferred in comparisons:
        if first_value != second_value:
            return (
                f"{label} is {first_value} versus {second_value}, and {preferred} "
                "ranks first under this heuristic"
            )
    return (
        f"all score components tie, so the stable opportunity ID "
        f"'{first.opportunity_id}' wins before '{second.opportunity_id}'"
    )


def _benchmark(
    business: BusinessInput,
    entities: tuple[MarketEntity, ...],
    target_evidence: tuple[SourceEvidence, ...],
    evidence_by_id: dict[str, SourceEvidence],
    website_inspection: WebsiteInspectionResult | None,
) -> MarketPosition:
    comparables = tuple(
        sorted(
            (
                entity
                for entity in entities
                if entity.entity_type is MarketEntityType.COMPETITOR
                and _industry_compatible(entity, business, evidence_by_id)
                and _location_compatible(entity, business, evidence_by_id)
            ),
            key=lambda item: item.entity_id,
        )
    )
    limitations: list[str] = [
        "The competitor list is a discovery sample, not a complete market census or market-share estimate."
    ]
    for entity in entities:
        if entity.entity_type is not MarketEntityType.COMPETITOR:
            continue
        _, category_status = _entity_field_evidence(
            entity, "category", entity.category, evidence_by_id
        )
        if category_status != "supported":
            limitations.append(
                _entity_fit_limitation(entity, "competitor comparison", category_status)
            )
        elif not _industry_compatible(entity, business, evidence_by_id):
            limitations.append(
                f"{entity.name} was excluded from competitor comparison because its supported category does not match {business.industry}."
            )
        else:
            location_ok, location_status = _entity_location_compatible(
                entity, business, evidence_by_id
            )
            if not location_ok:
                limitations.append(
                    _entity_fit_limitation(
                        entity, "competitor comparison", location_status
                    )
                )
    if len(comparables) < 2:
        limitations.append(
            "Fewer than two comparable competitors have direct source evidence; no relative ranking was made."
        )

    strengths: list[MarketFinding] = []
    weaknesses: list[MarketFinding] = []
    metrics_compared: list[str] = []
    coverage: list[DataCoverage] = [
        DataCoverage(
            "comparable_competitors",
            bool(comparables),
            sample_size=len(comparables),
            notes=(
                "Matched by category and location from supplied discovery entities."
                if comparables
                else "No directly supported competitor matched the business category and area."
            ),
        )
    ]

    for field in ("rating", "review_count"):
        target_value, target_ids, target_status = _observed_target_metric(
            target_evidence, field
        )
        peer_rows: list[tuple[MarketEntity, int | float, tuple[str, ...]]] = []
        conflicting_peers: list[str] = []
        invalid_peers: list[tuple[MarketEntity, str]] = []
        for entity in comparables:
            peer_value, peer_ids, peer_status = _observed_entity_metric(
                entity, field, evidence_by_id
            )
            if peer_value is not None:
                peer_rows.append((entity, peer_value, peer_ids))
            elif peer_status == "conflicting":
                conflicting_peers.append(entity.name)
            elif peer_status != "missing":
                invalid_peers.append((entity, peer_status))
        peer_values = tuple(peer_rows)
        coverage.append(
            DataCoverage(
                f"business_{field}",
                target_status != "missing",
                sample_size=1 if target_value is not None else 0,
                notes=_metric_status_note("business", field, target_status),
            )
        )
        coverage.append(
            DataCoverage(
                f"competitor_{field}",
                bool(peer_values) or bool(conflicting_peers) or bool(invalid_peers),
                sample_size=len(peer_values),
                notes=_metric_status_note(
                    "competitor",
                    field,
                    "conflicting"
                    if conflicting_peers
                    else "supported"
                    if peer_values
                    else invalid_peers[0][1]
                    if invalid_peers
                    else "missing",
                ),
            )
        )
        if target_status == "conflicting":
            limitations.append(
                f"Conflicting business {field} evidence was supplied; it was excluded from comparison until reconciled."
            )
        if conflicting_peers:
            limitations.append(
                f"Conflicting competitor {field} evidence for {', '.join(sorted(conflicting_peers))} was excluded from comparison."
            )
        for entity, peer_status in invalid_peers:
            limitations.append(
                f"{entity.name} {field} evidence was excluded: {_metric_status_note('competitor', field, peer_status)}"
            )
        if target_status not in {"missing", "supported", "conflicting"}:
            limitations.append(_metric_status_note("business", field, target_status))
        if target_value is None or len(peer_values) < 2 or len(comparables) < 2:
            continue
        metrics_compared.append(field)
        values = tuple(item[1] for item in peer_values)
        peer_min = min(values)
        peer_max = max(values)
        peer_ids = tuple(evidence_id for item in peer_values for evidence_id in item[2])
        referenced = tuple(sorted(set((*target_ids, *peer_ids))))
        label = "rating" if field == "rating" else "public review count"
        format_value = _format_metric
        description = f"Observed business {label} {format_value(target_value)}; observed comparable values range from {format_value(peer_min)} to {format_value(peer_max)} across {len(peer_values)} competitors. This comparison does not rank service quality or market share."
        if target_value > peer_max:
            strengths.append(
                MarketFinding(
                    f"Observed {label} is above this sample", description, referenced
                )
            )
        elif target_value < peer_min:
            weaknesses.append(
                MarketFinding(
                    f"Observed {label} is below this sample", description, referenced
                )
            )

    if not metrics_compared:
        limitations.append(
            "No rating or review metric had matching OBSERVED evidence for both the business and at least two comparable competitors; no benchmark score was assigned."
        )

    website_available = bool(website_inspection and website_inspection.signals)
    coverage.extend(
        (
            DataCoverage(
                "website_inspection",
                website_available,
                sample_size=(
                    len(website_inspection.signals)
                    if website_inspection is not None
                    else 0
                ),
                notes=(
                    "Structured inspection signals were supplied."
                    if website_inspection is not None and website_inspection.signals
                    else "Inspection was supplied without structured signals."
                    if website_inspection is not None
                    else "Website contents were not inspected."
                ),
            ),
            DataCoverage(
                "website_status",
                business.website_url is not None
                or bool(_field_records(target_evidence, "website_presence"))
                or bool(website_inspection and website_inspection.signals),
                sample_size=1
                if business.website_url is not None
                or _field_records(target_evidence, "website_presence")
                or bool(website_inspection and website_inspection.signals)
                else 0,
                notes=_website_status_note(
                    business, target_evidence, website_inspection
                ),
            ),
            DataCoverage(
                "service_area",
                business.service_radius_miles is not None
                or bool(_field_records(target_evidence, "service_area")),
                sample_size=1 if business.service_radius_miles is not None else 0,
                notes=(
                    "A service radius or service-area evidence was supplied."
                    if business.service_radius_miles is not None
                    or _field_records(target_evidence, "service_area")
                    else "Service coverage beyond the stated business location is unknown."
                ),
            ),
            DataCoverage(
                "google_business_profile_status",
                business.google_business_url is not None
                or bool(
                    _field_records(target_evidence, "google_business_profile_present")
                ),
                sample_size=1
                if business.google_business_url is not None
                or _field_records(target_evidence, "google_business_profile_present")
                else 0,
                notes=_profile_status_note(business, target_evidence),
            ),
            DataCoverage(
                "business_funnel_inputs",
                any(
                    getattr(business, field) is not None
                    for field in ("monthly_inquiries", "monthly_quotes", "monthly_jobs")
                ),
                sample_size=sum(
                    getattr(business, field) is not None
                    for field in ("monthly_inquiries", "monthly_quotes", "monthly_jobs")
                ),
                notes="If supplied, these values are owner-reported and were not used to calculate conversion or financial loss.",
            ),
        )
    )

    return MarketPosition(
        comparable_competitor_ids=tuple(item.entity_id for item in comparables),
        comparison_sample_size=len(comparables),
        metrics_compared=tuple(metrics_compared),
        relative_strengths=tuple(strengths),
        relative_weaknesses=tuple(weaknesses),
        market_gaps=(),
        data_coverage=tuple(coverage),
        limitations=tuple(limitations),
    )


def _observed_target_metric(
    evidence: tuple[SourceEvidence, ...], field: str
) -> tuple[int | float | None, tuple[str, ...], str]:
    rows = tuple(
        item
        for item in evidence
        if item.field == field and item.owner_entity_id is None
    )
    if not rows:
        return None, (), "missing"
    values = {(type(item.value), item.value) for item in rows}
    if len(values) > 1:
        return None, (), "conflicting"
    observed_rows = tuple(
        item
        for item in rows
        if item.kind is EvidenceKind.OBSERVED
        and type(item.value) in (int, float)
        and not isinstance(item.value, bool)
    )
    if not observed_rows:
        return None, (), "missing_observed"
    value = observed_rows[0].value
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None, (), "missing_observed"
    return value, tuple(sorted(item.evidence_id for item in observed_rows)), "supported"


def _observed_entity_metric(
    entity: MarketEntity,
    field: str,
    evidence_by_id: dict[str, SourceEvidence],
) -> tuple[int | float | None, tuple[str, ...], str]:
    value = getattr(entity, field)
    rows = tuple(
        evidence_by_id[evidence_id]
        for evidence_id in entity.evidence_ids
        if evidence_id in evidence_by_id
        and evidence_by_id[evidence_id].owner_entity_id == entity.entity_id
        and evidence_by_id[evidence_id].field == field
    )
    if not rows:
        return None, (), "missing"
    subject_rows = tuple(
        item for item in rows if _subject_matches(item.subject, entity.name)
    )
    if not subject_rows:
        return None, (), "subject_mismatch"
    values = {(type(item.value), item.value) for item in subject_rows}
    if len(values) > 1:
        return None, (), "conflicting"
    if (
        value is None
        or not values
        or _entity_value_key(field, value)
        not in {_entity_value_key(field, item.value) for item in subject_rows}
    ):
        return None, (), "value_mismatch"
    observed_rows = tuple(
        item
        for item in subject_rows
        if item.kind is EvidenceKind.OBSERVED
        and type(item.value) in (int, float)
        and not isinstance(item.value, bool)
    )
    if not observed_rows:
        return None, (), "missing_observed"
    observed_value = observed_rows[0].value
    if not isinstance(observed_value, (int, float)) or isinstance(observed_value, bool):
        return None, (), "missing_observed"
    return (
        observed_value,
        tuple(sorted(item.evidence_id for item in observed_rows)),
        "supported",
    )


def _metric_status_note(scope: str, field: str, status: str) -> str:
    if status == "supported":
        return f"Matching OBSERVED {scope} {field} evidence is available."
    if status == "conflicting":
        return (
            f"Conflicting {scope} {field} evidence was supplied; no value was selected."
        )
    if status == "missing_observed":
        return f"{scope.capitalize()} {field} evidence exists, but no matching OBSERVED value is available."
    if status == "subject_mismatch":
        return f"{scope.capitalize()} {field} evidence does not identify this entity."
    if status == "value_mismatch":
        return f"{scope.capitalize()} {field} evidence does not match the entity attribute."
    return f"No matching {scope} {field} evidence was supplied."


def _industry_compatible(
    entity: MarketEntity,
    business: BusinessInput,
    evidence_by_id: dict[str, SourceEvidence],
) -> bool:
    _, evidence_status = _entity_field_evidence(
        entity, "category", entity.category, evidence_by_id
    )
    if entity.category is None or evidence_status != "supported":
        return False
    profile = vertical_profile_for(business.industry)
    legacy_cleaning_key = (
        business.industry.casefold().replace("_", " ").strip() == "house cleaning"
    )
    industry = (
        "House Cleaning"
        if legacy_cleaning_key
        else profile.canonical_industry_name
        if profile is not None
        else business.industry
    )
    return _canonical_category(entity.category) == _canonical_category(industry)


def _location_compatible(
    entity: MarketEntity,
    business: BusinessInput,
    evidence_by_id: dict[str, SourceEvidence],
) -> bool:
    return _entity_location_compatible(entity, business, evidence_by_id)[0]


def _market_observations(
    entities: tuple[MarketEntity, ...],
    evidence_by_id: dict[str, SourceEvidence],
    business: BusinessInput,
) -> tuple[MarketStructureObservation, ...]:
    observations: list[MarketStructureObservation] = []
    competitors = tuple(
        item
        for item in entities
        if item.entity_type is MarketEntityType.COMPETITOR
        and _industry_compatible(item, business, evidence_by_id)
        and _location_compatible(item, business, evidence_by_id)
    )
    if competitors:
        observations.append(
            MarketStructureObservation(
                MarketStructureDimension.COMPETITIVE_RIVALRY,
                f"The supplied local discovery sample contains {len(competitors)} competitor listings; it does not establish total market density, market share, or competitive intensity.",
                tuple(
                    sorted(
                        {
                            evidence_id
                            for entity in competitors
                            for evidence_id in _entity_listing_evidence_ids(
                                entity, business, evidence_by_id
                            )
                        }
                    )
                ),
            )
        )
    suppliers = tuple(
        item
        for item in entities
        if item.entity_type is MarketEntityType.SUPPLIER
        and _supplier_entity_supported(item, business, evidence_by_id)[0]
    )
    if suppliers:
        observations.append(
            MarketStructureObservation(
                MarketStructureDimension.SUPPLIER_ALTERNATIVES,
                f"The supplied discovery sample contains {len(suppliers)} supplier listings; it does not establish current supplier use, comparable products, pricing, or dependence.",
                tuple(
                    sorted(
                        {
                            evidence_id
                            for entity in suppliers
                            for evidence_id in _entity_listing_evidence_ids(
                                entity, business, evidence_by_id
                            )
                        }
                    )
                ),
            )
        )
    substitute_rows = tuple(
        item
        for item in evidence_by_id.values()
        if item.field == "substitute"
        and item.kind is EvidenceKind.OBSERVED
        and item.owner_entity_id is None
        and _subject_matches(item.subject, business.business_name)
    )
    if substitute_rows:
        observations.append(
            MarketStructureObservation(
                MarketStructureDimension.SUBSTITUTES,
                "Observed evidence describes a possible substitute for the business's service; the assessment does not infer how often customers choose it.",
                tuple(sorted(item.evidence_id for item in substitute_rows)),
            )
        )
    return tuple(observations)


def _general_limitations(
    business: BusinessInput,
    target_evidence: tuple[SourceEvidence, ...],
    website_inspection: WebsiteInspectionResult | None,
) -> tuple[str, ...]:
    limitations: list[str] = []
    website_presence = _consistent_field_records(target_evidence, "website_presence")
    if website_presence is None:
        limitations.append(
            "Website status has conflicting source values; no absence or presence claim was made."
        )
    elif (
        business.website_url is None
        and not website_presence
        and (website_inspection is None or not website_inspection.signals)
    ):
        limitations.append(
            "No website URL or explicit website-presence status was supplied; this does not establish that the business has no website."
        )
    elif business.website_url is not None and (
        website_inspection is None or not website_inspection.signals
    ):
        limitations.append(
            "A website URL was supplied, but the site itself was not inspected."
        )
    if not any(
        getattr(business, field) is not None
        for field in (
            "monthly_inquiries",
            "monthly_quotes",
            "monthly_jobs",
            "average_job_value",
        )
    ):
        limitations.append(
            "No business performance or job-value inputs were supplied; no revenue, conversion rate, or financial loss was estimated."
        )
    elif any(
        getattr(business, field) is not None
        for field in (
            "monthly_inquiries",
            "monthly_quotes",
            "monthly_jobs",
            "average_job_value",
        )
    ):
        limitations.append(
            "Any performance or job-value figures supplied by the owner remain unverified and were not converted into revenue or loss estimates."
        )
    limitations.append(
        "Urgency, implementation dependencies, supplier pricing, and expected commercial outcomes were not ranked because the supplied evidence does not establish them."
    )
    return tuple(limitations)


def _field_records(
    evidence: tuple[SourceEvidence, ...], field: str
) -> tuple[SourceEvidence, ...]:
    return tuple(
        item
        for item in evidence
        if item.field == field and item.owner_entity_id is None
    )


def _profile_status_note(
    business: BusinessInput, target_evidence: tuple[SourceEvidence, ...]
) -> str:
    records = _consistent_field_records(
        target_evidence, "google_business_profile_present"
    )
    if records is None:
        return "Conflicting source values were supplied for profile presence."
    if business.google_business_url is not None:
        if records and any(item.value is False for item in records):
            return (
                "A supplied profile URL conflicts with evidence reporting no profile."
            )
        return "A Google Business Profile URL was supplied by the business; listing quality was not independently inspected."
    if not records:
        return "Profile status was not supplied or inspected; no absence is assumed."
    if records[0].value is True and records[0].kind is EvidenceKind.OBSERVED:
        return "Profile presence was observed in a supplied source."
    if records[0].value is False and records[0].kind is EvidenceKind.OBSERVED:
        return "Profile absence was observed in a supplied source."
    if records[0].value is False and records[0].kind is EvidenceKind.REPORTED:
        return "The business owner reports no profile; this has not been independently verified."
    if records[0].value is True and records[0].kind is EvidenceKind.REPORTED:
        return "The business owner reports a profile; this has not been independently verified."
    return "A profile status was supplied, but its source does not confirm presence or absence."


def _website_status_note(
    business: BusinessInput,
    target_evidence: tuple[SourceEvidence, ...],
    website_inspection: WebsiteInspectionResult | None,
) -> str:
    records = _consistent_field_records(target_evidence, "website_presence")
    if records is None:
        return "Conflicting evidence was supplied for website presence."
    if business.website_url is not None:
        if records and records[0].value is False:
            return (
                "A supplied website URL conflicts with evidence reporting no website."
            )
        if website_inspection is not None and website_inspection.signals:
            return "The business supplied a URL and structured website inspection evidence was provided."
        if website_inspection is not None:
            return "The business supplied a URL, but the inspection result contains no structured signals."
        return "The business supplied a URL; the page was not inspected."
    if records:
        record = records[0]
        if record.value is False and record.kind is EvidenceKind.OBSERVED:
            return "A supplied source observed no website."
        if record.value is False and record.kind is EvidenceKind.REPORTED:
            return "The business owner reports no website; this was not independently verified."
        if record.value is True and record.kind is EvidenceKind.OBSERVED:
            return "A supplied source observed a website."
        if record.value is True and record.kind is EvidenceKind.REPORTED:
            return "The business owner reports a website; it was not independently verified."
    if website_inspection is not None and website_inspection.signals:
        return "Inspection evidence was supplied, but the business URL field is empty."
    if website_inspection is not None:
        return "The inspection result contains no structured signals; website status remains unknown."
    return "Website status was not supplied or inspected; absence is not confirmed."


def _coverage_note(assessment: BusinessAssessment, signal: str) -> str | None:
    for coverage in assessment.market_position.data_coverage:
        if coverage.signal == signal:
            return coverage.notes
    return None


def _next_information_to_collect(assessment: BusinessAssessment) -> tuple[str, ...]:
    next_steps: list[str] = []
    coverage = {item.signal: item for item in assessment.market_position.data_coverage}
    comparable_coverage = coverage.get("comparable_competitors")
    comparable_count = (
        comparable_coverage.sample_size or 0 if comparable_coverage else 0
    )
    if comparable_count < 2:
        if comparable_count == 1:
            next_steps.append(
                "Provide at least one additional source-backed competitor matched to the business's services and area before comparing the sample."
            )
        else:
            next_steps.append(
                "Provide a source-backed local competitor sample matched to the business's services and area."
            )
    website_coverage = coverage.get("website_inspection")
    if website_coverage is None or not website_coverage.available:
        if assessment.business.website_url is None:
            next_steps.append(
                "Confirm whether a public website exists and provide its URL; a missing URL here is not proof of absence."
            )
        else:
            next_steps.append(
                "Inspect the supplied website's contact and quote-request paths and provide structured signal-level results."
            )
    if not coverage.get(
        "google_business_profile_status", DataCoverage("x", False)
    ).available:
        next_steps.append(
            "Confirm whether a Google Business Profile exists and provide its public URL if available."
        )
    if not coverage.get("service_area", DataCoverage("x", False)).available:
        next_steps.append(
            "Provide the services offered and the geographic area the business can serve."
        )
    if not coverage.get("business_funnel_inputs", DataCoverage("x", False)).available:
        next_steps.append(
            "If business-specific impact is needed, provide same-period inquiry, quote, and completed-job counts; no financial impact is estimated without them."
        )
    for signal, label in (
        ("google_business_profile_status", "Google Business Profile presence"),
        ("business_rating", "business rating"),
        ("business_review_count", "business review count"),
        ("competitor_rating", "competitor ratings"),
        ("competitor_review_count", "competitor review counts"),
    ):
        item = coverage.get(signal)
        if item is not None and item.notes and "conflicting" in item.notes.casefold():
            next_steps.append(
                f"Reconcile the conflicting source records for {label} and provide one current, attributable value."
            )
    if not next_steps:
        next_steps.append(
            "Verify the source records and outcome measures before acting on the assessment."
        )
    return tuple(next_steps)


def _display_value(value: JsonScalar) -> str:
    if value is None:
        return "unknown"
    if type(value) is bool:
        return "yes" if value else "no"
    return str(value)


def _format_metric(value: int | float) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _normalize_state(value: str) -> str:
    normalized = _normalize_text(value)
    if normalized in _US_STATE_CODES:
        return _US_STATE_CODES[normalized]
    return normalized


def _same_scalar(left: JsonScalar, right: JsonScalar) -> bool:
    return type(left) is type(right) and left == right
