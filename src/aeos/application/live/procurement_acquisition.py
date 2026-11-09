"""Read-only procurement acquisition reporting over the existing LIVE contracts."""

from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any
from urllib.parse import quote

from aeos.application.tenancy import GetBusinessProfileForTenant
from aeos.live.adapters.manatee_procurement import (
    AcquisitionState,
    ManateeProcurementBatch,
    RecordOrigin,
    SolicitationImport,
    deadline_disposition,
    opportunity_for_import,
)
from aeos.live.domain.opportunity_inbox import (
    DemandType,
    LeadClassification,
    Opportunity,
    OpportunityAssessment,
    PermissionBasis,
    ProcurementStatus,
    SourceProvenance,
    classify_opportunity,
    score_opportunity_preview,
)
from aeos.live.domain.evidence import EvidenceKind, SourceEvidence
from aeos.live.domain.profile import BusinessProfile
from aeos.tenancy.domain import TenantPrincipal
from aeos.tenancy.errors import BusinessProfileNotFound, TenantAccessDenied
from aeos.core.ids import OrganizationId


def build_acquisition_report(
    batch: ManateeProcurementBatch,
    *,
    as_of: date,
    profile: BusinessProfile | None = None,
    profile_status: str | None = None,
    organization_id: OrganizationId | None = None,
) -> dict[str, object]:
    """Create an evidence-led report; imported values stay non-observed."""

    if profile_status is None:
        profile_status = "AVAILABLE" if profile is not None else "UNAVAILABLE"
    entries: list[dict[str, object]] = []
    classifications: list[LeadClassification] = []
    all_records = (*batch.solicitations, *batch.secondary_candidates)
    for record in all_records:
        assessment: OpportunityAssessment | None = None
        decision = "PENDING_PRIMARY_SOURCE"
        if record.origin is RecordOrigin.MANUAL_OFFICIAL_IMPORT:
            opportunity = opportunity_for_import(record)
            if opportunity is not None:
                assessment = classify_opportunity(
                    opportunity,
                    as_of=as_of,
                    organization_profile=profile,
                )
                classifications.append(assessment.classification)
                if assessment.classification is LeadClassification.EXPIRED:
                    decision = "EXPIRED"
                elif assessment.classification is LeadClassification.COLD:
                    decision = "INCOMPATIBLE"
                elif assessment.classification in {
                    LeadClassification.HOT,
                    LeadClassification.WARM,
                }:
                    decision = "COMPATIBLE_REQUIRES_OWNER_REVIEW"
                else:
                    decision = "PENDING_REVIEW"
        entries.append(
            _serialize_record(
                record,
                decision=decision,
                assessment=assessment,
                profile=profile,
                as_of=as_of,
            )
        )

    compatible = sum(
        item in {LeadClassification.HOT, LeadClassification.WARM}
        for item in classifications
    )
    incompatible = sum(item is LeadClassification.COLD for item in classifications)
    expired = sum(item is LeadClassification.EXPIRED for item in classifications)
    pending = len(entries) - compatible - incompatible - expired
    return {
        "schema_version": 1,
        "generated_for_date": as_of.isoformat(),
        "source": {
            "name": "Manatee County Bids and Proposals",
            "agency": "Manatee County",
            "starting_url": batch.source_url,
            "access_mode": batch.access_mode,
            "response_state": (
                batch.response_state.value if batch.response_state else "UNKNOWN"
            ),
            "acquisition_state": batch.state.value,
            "retrieved_at": batch.retrieved_at.isoformat(),
            "block_reason": batch.block_reason or "UNKNOWN",
            "malformed_reason": batch.malformed_reason or "UNKNOWN",
        },
        "tenant_profile": {
            "status": profile_status,
            "organization_id": (
                str(organization_id) if organization_id is not None else "UNKNOWN"
            ),
            "loaded_through": (
                "GetBusinessProfileForTenant" if profile is not None else "UNKNOWN"
            ),
        },
        "counts": {
            "manually_imported_official_records": len(batch.solicitations),
            "secondary_discovery_candidates": len(batch.secondary_candidates),
            "observed_by_adapter": 0,
            "verified_against_official_source": 0,
            "compatible": compatible,
            "incompatible": incompatible,
            "expired": expired,
            "pending_review": pending,
            "exact_duplicates_removed": batch.exact_duplicates_removed,
            "possible_url_matches_requiring_review": len(batch.possible_url_matches),
        },
        "deduplication": {
            "method": "issuing agency + solicitation identifier",
            "url_role": "normalized URL is supplementary evidence only",
            "possible_url_matches": [
                {"left": left, "right": right}
                for left, right in batch.possible_url_matches
            ],
        },
        "opportunities": entries,
        "market_state_note": (
            "A BLOCKED source is not an empty market. No live solicitation was "
            "reported as observed by this adapter."
            if batch.state is AcquisitionState.BLOCKED
            else "Manually imported claims are reported, not independently observed."
        ),
    }


def build_tenant_acquisition_report(
    batch: ManateeProcurementBatch,
    *,
    as_of: date,
    profile_reader: GetBusinessProfileForTenant,
    principal: TenantPrincipal,
    organization_id: OrganizationId,
) -> dict[str, object]:
    """Load the profile through AEOS's authorized tenant-owned read use case."""

    try:
        profile = profile_reader.execute(principal, organization_id)
    except BusinessProfileNotFound:
        return build_acquisition_report(
            batch,
            as_of=as_of,
            profile_status="PROFILE_NOT_FOUND",
            organization_id=organization_id,
        )
    except TenantAccessDenied:
        return build_acquisition_report(
            batch,
            as_of=as_of,
            profile_status="ACCESS_DENIED",
            organization_id=organization_id,
        )
    return build_acquisition_report(
        batch,
        as_of=as_of,
        profile=profile,
        profile_status="AVAILABLE",
        organization_id=organization_id,
    )


def build_synthetic_profile_preview(
    profile: BusinessProfile, *, as_of: date
) -> dict[str, object]:
    """Exercise the existing source-independent scorer with an explicit fixture."""

    if not profile.is_fictional_example:
        raise ValueError("synthetic previews require a fictional business profile")
    if not profile.primary_services:
        return {
            "scenario": "SYNTHETIC_ONLY",
            "status": "NOT_SCORED",
            "reason": "The synthetic profile has no configured primary services.",
            "actionable": False,
            "business_profile": profile.business_name,
        }
    observed_at = datetime.now(timezone.utc)
    opportunity_id = "synthetic-preview:manatee-procurement"
    values: tuple[tuple[str, object], ...] = (
        ("city", profile.city),
        ("state", profile.state_region),
        ("service_requested", profile.primary_services[0]),
        ("explicit_intent", True),
        ("publication_date", as_of.isoformat()),
        ("open_status", True),
        ("procurement_status", ProcurementStatus.OPEN_SOLICITATION.value),
        ("response_method", "Synthetic manual procurement response channel"),
        ("expected_jobs_per_day", 1),
    )
    evidence = tuple(
        SourceEvidence(
            evidence_id=f"{opportunity_id}:{field_name}",
            kind=EvidenceKind.REPORTED,
            subject=opportunity_id,
            field=field_name,
            value=value,  # type: ignore[arg-type]
            source_name="Synthetic demonstration data",
            source_url="https://www.mymanatee.org/",
            retrieved_at=None,
            excerpt="Fabricated demonstration value; not a real solicitation.",
            confidence=0.95,
            owner_entity_id=opportunity_id,
        )
        for field_name, value in values
    )
    opportunity = Opportunity(
        opportunity_id=opportunity_id,
        title="SYNTHETIC DEMONSTRATION — NOT A REAL SOLICITATION",
        source_platform="Synthetic demonstration data",
        demand_type=DemandType.PUBLIC_PROCUREMENT,
        publication_date=as_of,
        discovered_at=observed_at,
        service_requested=profile.primary_services[0],
        summary="Fabricated data used only to demonstrate profile-independent scoring.",
        source_url="https://www.mymanatee.org/",
        source_event_ref=None,
        city=profile.city,
        state=profile.state_region,
        explicit_intent=True,
        is_open=True,
        response_method="Synthetic manual procurement response channel",
        publicly_accessible=True,
        business_authorized=True,
        account_holder_authorized=False,
        permission_basis=PermissionBasis.PUBLIC_NOTICE,
        source_terms_note="Synthetic demonstration only; no source access occurred.",
        procurement_status=ProcurementStatus.OPEN_SOLICITATION,
        official_deadline=None,
        eligibility_requirements=(),
        expected_jobs_per_day=1,
        ongoing_need=False,
        limitations=("Synthetic scenario; not an observed business opportunity.",),
        evidence=evidence,
        stable_request_id="synthetic-demo-only",
        source_provenance=SourceProvenance.SYNTHETIC,
    )
    assessment = score_opportunity_preview(
        opportunity,
        as_of=as_of,
        organization_profile=profile,
    )
    return {
        "scenario": "SYNTHETIC_ONLY",
        "status": assessment.classification.value,
        "actionable": assessment.actionable,
        "business_profile": profile.business_name,
        "vertical": profile.vertical,
        "commercial_fit_score": assessment.commercial_fit_score,
        "classification_reasons": list(assessment.classification_reasons_es),
        "recommended_action": assessment.recommended_action_es,
        "capacity_review_required": assessment.capacity_review_required,
        "note": (
            "This preview uses a fictional profile and fabricated solicitation. "
            "It is not market evidence and cannot become actionable."
        ),
    }


def render_acquisition_markdown(report: dict[str, object]) -> str:
    """Render a concise operator report with the evidence limits made visible."""

    source = _dict(report.get("source"))
    counts = _dict(report.get("counts"))
    tenant = _dict(report.get("tenant_profile"))
    lines = [
        "# Manatee County Procurement Acquisition",
        "",
        f"- Acquisition state: **{source.get('acquisition_state', 'UNKNOWN')}**",
        f"- Access mode: **{source.get('access_mode', 'UNKNOWN')}**",
        f"- Source response: **{source.get('response_state', 'UNKNOWN')}**",
        f"- Tenant profile: **{tenant.get('status', 'UNKNOWN')}**",
        f"- Manually imported official records: **{counts.get('manually_imported_official_records', 0)}**",
        f"- Secondary discovery candidates: **{counts.get('secondary_discovery_candidates', 0)}**",
        f"- Observed by adapter: **{counts.get('observed_by_adapter', 0)}**",
        f"- Verified against official source: **{counts.get('verified_against_official_source', 0)}**",
        f"- Compatible / incompatible / expired / pending review: "
        f"**{counts.get('compatible', 0)} / {counts.get('incompatible', 0)} / "
        f"{counts.get('expired', 0)} / {counts.get('pending_review', 0)}**",
        "",
        str(report.get("market_state_note", "")),
        "",
    ]
    if source.get("block_reason") != "UNKNOWN":
        lines.extend(
            [f"Source access note: {_markdown_cell(source['block_reason'])}", ""]
        )
    opportunities = report.get("opportunities")
    if not isinstance(opportunities, list) or not opportunities:
        lines.extend(["No source records or secondary candidates were imported.", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "## Candidate review",
            "",
            "| Agency | Solicitation ID | Title | Decision | Deadline |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for raw in opportunities:
        item = _dict(raw)
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(item.get(key))
                for key in (
                    "issuing_agency",
                    "solicitation_id",
                    "title",
                    "decision",
                    "closing_date",
                )
            )
            + " |"
        )
    for raw in opportunities:
        item = _dict(raw)
        lines.extend(
            [
                "",
                f"### {_markdown_cell(item.get('title'))}",
                "",
                f"- Decision: **{item.get('decision', 'UNKNOWN')}**",
                f"- Reason: {item.get('decision_reason', 'UNKNOWN')}",
                f"- Deadline validity: **{item.get('deadline_validity', 'UNKNOWN')}**",
                f"- Owner review required: **{item.get('owner_review_required', True)}**",
                f"- Service fit: **{item.get('evaluation', {}).get('service_compatibility', 'UNKNOWN') if isinstance(item.get('evaluation'), dict) else 'UNKNOWN'}**",
                f"- Geographic fit: **{item.get('evaluation', {}).get('geographic_compatibility', 'UNKNOWN') if isinstance(item.get('evaluation'), dict) else 'UNKNOWN'}**",
            ]
        )
        references = item.get("evidence_references")
        if isinstance(references, list):
            lines.append("- Evidence references:")
            for reference in references:
                ref = _dict(reference)
                lines.append(
                    f"  - {ref.get('kind', 'UNKNOWN')}: "
                    f"[{_markdown_cell(ref.get('label'))}]"
                    f"({_markdown_destination(ref.get('url', ''))})"
                )
        qualification = item.get("qualification")
        if isinstance(qualification, dict):
            reasons = qualification.get("classification_reasons")
            if isinstance(reasons, list) and reasons:
                lines.append("- AEOS qualification reasons:")
                lines.extend(f"  - {_markdown_cell(reason)}" for reason in reasons)
    lines.append("")
    return "\n".join(lines)


def _serialize_record(
    record: SolicitationImport,
    *,
    decision: str,
    assessment: OpportunityAssessment | None,
    profile: BusinessProfile | None,
    as_of: date,
) -> dict[str, object]:
    if decision == "PENDING_PRIMARY_SOURCE":
        reason = (
            "The candidate is supported only by secondary discovery references; "
            "retrieve and verify the original Manatee County record."
        )
    elif assessment is not None:
        reason = (
            "The record was manually imported and has not been observed or verified "
            "by this adapter; AEOS requires primary-source evidence before qualification."
        )
    else:
        reason = "Primary-source verification is required before qualification."

    verified_primary = False
    evaluation = {
        "service_compatibility": (
            "PENDING_PRIMARY_SOURCE"
            if record.origin is RecordOrigin.SECONDARY_DISCOVERY
            else "PENDING_EVIDENCE"
            if profile is not None
            else "PROFILE_UNAVAILABLE"
        ),
        "geographic_compatibility": (
            "PENDING_PRIMARY_SOURCE"
            if record.origin is RecordOrigin.SECONDARY_DISCOVERY
            else "PENDING_EVIDENCE"
            if profile is not None
            else "PROFILE_UNAVAILABLE"
        ),
        "evidence_quality": (
            "SECONDARY_ONLY"
            if not record.has_primary_reference
            else "MANUALLY_IMPORTED_UNVERIFIED"
        ),
        "actual_buying_solicitation": (
            "UNKNOWN" if record.buying_solicitation is None else "REPORTED"
        ),
        "deadline_validity": deadline_disposition(
            record.closing_date,
            primary_source_verified=verified_primary,
            as_of=as_of,
        ),
        "eligibility_and_operational_restrictions": "OWNER_REVIEW_REQUIRED",
    }
    qualification: dict[str, object] | None = None
    if assessment is not None:
        qualification = {
            "classification": assessment.classification.value,
            "commercial_fit_score": assessment.commercial_fit_score,
            "classification_reasons": list(assessment.classification_reasons_es),
            "recommended_action": assessment.recommended_action_es,
            "capacity_review_required": assessment.capacity_review_required,
            "score_components": [
                {
                    "key": component.key,
                    "score": component.score,
                    "maximum": component.maximum,
                    "explanation": component.explanation_es,
                    "evidence_ids": list(component.evidence_ids),
                }
                for component in assessment.score_components
            ],
        }
    return {
        "issuing_agency": _unknown(record.issuing_agency),
        "solicitation_id": _unknown(record.solicitation_id),
        "title": _unknown(record.title),
        "description": _unknown(record.description),
        "official_source_url": _unknown(record.official_source_url),
        "publication_date": _unknown(
            record.publication_date.isoformat() if record.publication_date else None
        ),
        "closing_date": _unknown(
            record.closing_date.isoformat() if record.closing_date else None
        ),
        "closing_time_local": _unknown(record.closing_time_local),
        "closing_timezone": _unknown(record.closing_timezone),
        "location": _unknown(record.location),
        "city": _unknown(record.city),
        "state": _unknown(record.state),
        "publication_status": _unknown(record.publication_status),
        "service_categories": (
            list(record.service_categories) if record.service_categories else "UNKNOWN"
        ),
        "eligibility_requirements": (
            list(record.eligibility_requirements)
            if record.eligibility_requirements
            else "UNKNOWN"
        ),
        "operational_restrictions": (
            list(record.operational_restrictions)
            if record.operational_restrictions
            else "UNKNOWN"
        ),
        "buying_solicitation": (
            record.buying_solicitation
            if record.buying_solicitation is not None
            else "UNKNOWN"
        ),
        "source_access_mode": record.origin.value,
        "retrieved_at": record.retrieved_at.isoformat(),
        "verification_state": (
            "PENDING_PRIMARY_SOURCE"
            if not record.has_primary_reference
            else "MANUALLY_IMPORTED_UNVERIFIED"
        ),
        "evidence_references": [
            {
                "reference_id": reference.reference_id,
                "kind": reference.kind.value,
                "url": reference.url,
                "label": reference.label,
                "fields": list(reference.fields),
                "excerpt": _unknown(reference.excerpt),
            }
            for reference in record.evidence_references
        ],
        "decision": decision,
        "decision_reason": reason,
        "deadline_validity": evaluation["deadline_validity"],
        "owner_review_required": True,
        "evaluation": evaluation,
        "qualification": qualification or "UNKNOWN",
        "duplicate_count": record.duplicate_count,
        "conflicting_fields": list(record.conflicting_fields),
    }


def _unknown(value: object) -> object:
    return "UNKNOWN" if value is None else value


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _markdown_cell(value: object) -> str:
    text = "UNKNOWN" if value is None else str(value)
    text = " ".join(text.split())
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~])", r"\\\1", text)


def _markdown_destination(value: object) -> str:
    return quote(str(value), safe=":/?#@!$&'*+,;=%-._~")


__all__ = [
    "build_acquisition_report",
    "build_synthetic_profile_preview",
    "build_tenant_acquisition_report",
    "render_acquisition_markdown",
]
