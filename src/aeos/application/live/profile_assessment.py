"""Application entry point for assessing a profile against a market sample."""

from aeos.application.live.assess_business import assess_business
from aeos.live.domain import (
    BusinessProfile,
    EvidenceKind,
    MarketEntityType,
    SourceEvidence,
    BusinessAssessment,
)
from aeos.live.ports import MarketDiscoveryResult


def _relationship_hypotheses(
    profile: BusinessProfile, discovery: MarketDiscoveryResult
) -> tuple[SourceEvidence, ...]:
    records: list[SourceEvidence] = []
    for entity in discovery.entities:
        roles: list[tuple[str, str, str]] = []
        if entity.entity_type is MarketEntityType.COMPETITOR:
            roles.append(
                (
                    "competitor_status",
                    "POTENTIAL_COMPETITOR",
                    "This category may indicate a competing service; exact service, segment, coverage, and business model remain unverified.",
                )
            )
        elif entity.entity_type is MarketEntityType.POTENTIAL_CUSTOMER:
            roles.append(
                (
                    "commercial_relationship_hypothesis",
                    "POTENTIAL_CUSTOMER",
                    "This organization category may need the business's services; need, outsourcing, authority, and buying intent remain unverified.",
                )
            )
            if entity.category == "property management":
                roles.append(
                    (
                        "commercial_relationship_hypothesis",
                        "POTENTIAL_PARTNER",
                        "A property manager may also be a referral or service channel; no relationship or referral agreement is established.",
                    )
                )
        elif entity.entity_type is MarketEntityType.PARTNER:
            roles.append(
                (
                    "commercial_relationship_hypothesis",
                    "POTENTIAL_PARTNER",
                    "This category may provide a customer referral route; shared customers and willingness to partner remain unverified.",
                )
            )
        elif entity.entity_type is MarketEntityType.SUPPLIER:
            roles.append(
                (
                    "commercial_relationship_hypothesis",
                    "POTENTIAL_SUPPLIER",
                    "This category may supply relevant products; assortment, stock, prices, delivery, and terms remain unverified.",
                )
            )

        category_evidence = next(
            (
                item
                for item in discovery.evidence
                if item.evidence_id in entity.evidence_ids and item.field == "category"
            ),
            None,
        )
        if category_evidence is None:
            continue
        for index, (field, value, excerpt) in enumerate(roles):
            records.append(
                SourceEvidence(
                    evidence_id=f"inference:{entity.entity_id}:{field}:{index}",
                    kind=EvidenceKind.INFERRED,
                    subject=entity.name,
                    field=field,
                    value=value,
                    source_name="AEOS LIVE documented category interpretation",
                    source_url=category_evidence.source_url,
                    retrieved_at=category_evidence.retrieved_at,
                    excerpt=excerpt,
                    assumptions=(
                        f"The observed provider category is {category_evidence.value!r}.",
                        f"The target business declared vertical {profile.vertical!r} and services {', '.join(profile.primary_services)!r}.",
                        "The category match is a research hypothesis and does not establish demand, service fit, or intent.",
                    ),
                )
            )
    return tuple(records)


def assess_business_profile(
    profile: BusinessProfile, discovery: MarketDiscoveryResult
) -> BusinessAssessment:
    """Run the established deterministic assessment with reported profile facts."""

    evidence = (
        *profile.reported_evidence(),
        *_relationship_hypotheses(profile, discovery),
    )
    return assess_business(profile.to_business_input(), discovery, evidence=evidence)


__all__ = ["assess_business_profile"]
