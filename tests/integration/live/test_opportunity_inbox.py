from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from aeos.live.adapters.opportunity_inbox import LocalOpportunityInbox
from aeos.application.live.opportunity_inbox import import_record
from aeos.application.tenancy import RegisterOrganization, TenantContextResolver
from aeos.core import ActorKind, ActorRef, OrganizationId
from aeos.organization.domain.organization import Organization
from aeos.tenancy.domain import TenantContext, TenantPrincipal
from aeos.live.domain.opportunity_inbox import (
    DuplicateMatchType,
    OpportunityStatus,
)
from aeos.live.opportunity_inbox_pilot import main


class _MemoryOrganizations:
    def __init__(self) -> None:
        self.values: dict[str, Organization] = {}

    def add(self, organization: Organization) -> None:
        self.values[organization.organization_id.value] = organization

    def get(self, organization_id: OrganizationId) -> Organization | None:
        return self.values.get(organization_id.value)

    def list_for_actor(self, actor: ActorRef) -> tuple[Organization, ...]:
        return tuple(
            organization
            for organization in self.values.values()
            if any(
                assignment.actor == actor
                for assignment in organization.assignments.values()
            )
        )


def _tenant_manager() -> TenantContext:
    organizations = _MemoryOrganizations()
    principal = TenantPrincipal(ActorRef(OrganizationId.new(), ActorKind.HUMAN))
    organization = RegisterOrganization(organizations).execute(
        principal, "Synthetic integration tenant"
    )
    return TenantContextResolver(organizations).resolve(
        principal, organization.organization_id
    )


def _payload(
    opportunity_id: str,
    source_url: str,
) -> dict[str, object]:
    evidence = [
        ("city", "Sample City Two"),
        ("state", "FL"),
        ("service_requested", "Residential cleaning"),
        ("explicit_intent", True),
        ("response_method", "Public source native response form"),
        ("publication_date", "2026-11-06"),
        ("open_status", True),
    ]
    return {
        "opportunity_id": opportunity_id,
        "title": "Move-out cleaning for 3 bedroom, 2 bathroom townhouse",
        "source_platform": "Facebook public Groups and Marketplace",
        "demand_type": "DIRECT_CUSTOMER_DEMAND",
        "publication_date": "2026-11-06",
        "discovered_at": "2026-11-07T16:00:00+00:00",
        "service_requested": "Residential cleaning",
        "summary": "Move-out clean for a 3 bedroom and 2 bathroom townhouse.",
        "source_url": source_url,
        "source_event_ref": None,
        "city": "Sample City Two",
        "state": "FL",
        "explicit_intent": True,
        "is_open": True,
        "response_method": "Public source native response form",
        "publicly_accessible": True,
        "business_authorized": True,
        "source_provenance": "REAL",
        "account_holder_authorized": False,
        "permission_basis": "PUBLIC_NOTICE",
        "source_terms_note": "Verified manual-source test control; no external action.",
        "procurement_status": None,
        "official_deadline": None,
        "eligibility_requirements": [],
        "expected_jobs_per_day": 1,
        "ongoing_need": False,
        "evidence": [
            {
                "field": field,
                "value": value,
                "kind": "OBSERVED",
                "confidence": 0.95,
                "excerpt": f"Observed test-source evidence for {field}.",
            }
            for field, value in evidence
        ],
    }


def test_cli_store_cross_source_dedup_and_lifecycle_gate(tmp_path: Path) -> None:
    store_path = tmp_path / "opportunities.json"
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text(
        json.dumps(
            _payload(
                "integration-request-a",
                "https://www.facebook.com/groups/source-a/posts/one",
            )
        ),
        encoding="utf-8",
    )
    second_path.write_text(
        json.dumps(
            _payload(
                "integration-request-b",
                "https://www.facebook.com/groups/source-b/posts/two",
            )
        ),
        encoding="utf-8",
    )

    unauthenticated_store = tmp_path / "unauthenticated-import.json"
    assert (
        main(
            [
                "import",
                "--input",
                str(first_path),
                "--store",
                str(unauthenticated_store),
            ]
        )
        == 2
    )
    assert not unauthenticated_store.exists()

    store = LocalOpportunityInbox(store_path)
    manager = _tenant_manager()
    for payload in (
        _payload(
            "integration-request-a",
            "https://www.facebook.com/groups/source-a/posts/one",
        ),
        _payload(
            "integration-request-b",
            "https://www.facebook.com/groups/source-b/posts/two",
        ),
    ):
        record = import_record(payload)
        store.add(
            record,
            operator_context=manager,
            attested_evidence_ids=tuple(
                item.evidence_id
                for item in record.opportunity.evidence
                if item.kind.value == "OBSERVED"
            ),
        )

    records = store.list_records()
    assert len(records) == 2
    root = next(
        item for item in records if item.status is not OpportunityStatus.DUPLICATE
    )
    duplicate = next(
        item for item in records if item.status is OpportunityStatus.DUPLICATE
    )
    assert duplicate.duplicate_of == root.opportunity.opportunity_id
    assert duplicate.duplicate_match is DuplicateMatchType.STRONG
    assert (
        duplicate.opportunity.source_url
        == "https://www.facebook.com/groups/source-b/posts/two"
    )

    before = store_path.read_bytes()
    assert (
        main(
            [
                "status",
                "--opportunity-id",
                root.opportunity.opportunity_id,
                "--status",
                "NEEDS_REVIEW",
                "--actor",
                "Synthetic owner",
                "--note",
                "Attempt lifecycle bypass",
                "--store",
                str(store_path),
            ]
        )
        == 2
    )
    assert store_path.read_bytes() == before

    assert (
        main(
            [
                "verify-open",
                "--opportunity-id",
                root.opportunity.opportunity_id,
                "--actor",
                "Synthetic owner",
                "--note",
                "Source rechecked in integration fixture",
                "--store",
                str(store_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "status",
                "--opportunity-id",
                root.opportunity.opportunity_id,
                "--status",
                "NEEDS_REVIEW",
                "--actor",
                "Synthetic owner",
                "--note",
                "Verified scope and source permission",
                "--store",
                str(store_path),
            ]
        )
        == 0
    )
    verified = store.get(root.opportunity.opportunity_id)
    assert verified is not None
    assert verified.status is OpportunityStatus.NEEDS_REVIEW
    assert verified.opportunity.publication_date == date(2026, 11, 6)
