"""Governance fact repositories; no evaluator or authorization logic is present."""

from __future__ import annotations

from typing import Any, Sequence, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from aeos.core import ActorRef, ApprovalDecisionId, VersionRef
from aeos.governance.domain import (
    ApprovalDecision,
    ApprovalRequest,
    GovernanceDecision,
    PermissionCapability,
    PermissionGrant,
    PermissionScope,
    PermissionScopeKind,
)
from aeos.governance.domain.permission import PermissionGrantee
from aeos.infrastructure.persistence import schema
from aeos.infrastructure.persistence.repositories import _insert, _one
from aeos.infrastructure.persistence.types import (
    ID_CLASSES,
    actor_from_values,
    actor_values,
    id_value,
    trace_from_values,
    trace_values,
)


def _versions(
    session: Session, table: Any, key: str, value: str
) -> tuple[VersionRef, ...]:
    return tuple(
        VersionRef(row["version_subject"], row["version"])
        for row in session.execute(
            select(table).where(table.c[key] == value).order_by(table.c.ordinal)
        ).mappings()
    )


def _write_versions(
    session: Session, table: Any, key: str, value: str, versions: tuple[VersionRef, ...]
) -> None:
    for ordinal, reference in enumerate(versions):
        _insert(
            session,
            table,
            {
                key: value,
                "ordinal": ordinal,
                "version_subject": reference.subject,
                "version": reference.version,
            },
        )


class PermissionGrantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: PermissionGrant) -> None:
        grantee_kind = None
        if isinstance(value.grantee, ActorRef):
            grantee_id, grantee_type, grantee_kind = actor_values(value.grantee)
        else:
            grantee_id = id_value(value.grantee)
            grantee_type = value.grantee.__class__.__name__
        constitution = value.constitution_version
        _insert(
            self._session,
            schema.permission_grants,
            {
                "id": id_value(value.permission_grant_id),
                "organization_id": id_value(value.organization_id),
                "grantee_id": grantee_id,
                "grantee_type": grantee_type,
                "grantee_kind": grantee_kind,
                "capability": value.capability.value,
                "scope_kind": value.scope.kind.value,
                "policy_subject": value.policy_version.subject,
                "policy_version": value.policy_version.version,
                "constitution_subject": None
                if constitution is None
                else constitution.subject,
                "constitution_version": None
                if constitution is None
                else constitution.version,
                "valid_from": value.valid_from,
                "valid_until": value.valid_until,
                "created_at": value.created_at,
                **trace_values(value.trace),
            },
        )

    def get(self, value_id: Any) -> PermissionGrant | None:
        row = _one(
            self._session,
            select(schema.permission_grants).where(
                schema.permission_grants.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import (
            OrganizationId,
            PermissionGrantId,
            RoleAssignmentId,
            RoleId,
        )

        grantee: PermissionGrantee
        if row["grantee_kind"] is not None:
            grantee = actor_from_values(
                row["grantee_id"], row["grantee_type"], row["grantee_kind"]
            )
        else:
            grantee_cls = ID_CLASSES.get(row["grantee_type"])
            if grantee_cls not in (RoleId, RoleAssignmentId):
                raise ValueError("invalid persisted permission grantee")
            grantee = cast(Any, grantee_cls.from_string(row["grantee_id"]))
        constitution = (
            None
            if row["constitution_subject"] is None
            else VersionRef(row["constitution_subject"], row["constitution_version"])
        )
        return PermissionGrant(
            PermissionGrantId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            grantee,
            PermissionCapability(row["capability"]),
            PermissionScope(PermissionScopeKind(row["scope_kind"])),
            VersionRef(row["policy_subject"], row["policy_version"]),
            constitution,
            row["valid_from"],
            row["valid_until"],
            row["created_at"],
            trace_from_values(row),
        )


class GovernanceDecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: GovernanceDecision) -> None:
        evaluated = (
            None
            if value.evaluated_actor is None
            else actor_values(value.evaluated_actor)
        )
        _insert(
            self._session,
            schema.governance_decisions,
            {
                "id": id_value(value.governance_decision_id),
                "organization_id": id_value(value.organization_id),
                "result": value.result.value,
                "reason": value.reason,
                "constitution_subject": value.constitution_version.subject,
                "constitution_version": value.constitution_version.version,
                "decided_at": value.decided_at,
                "evaluated_actor_id": None if evaluated is None else evaluated[0],
                "evaluated_actor_type": None if evaluated is None else evaluated[1],
                "evaluated_actor_kind": None if evaluated is None else evaluated[2],
                **trace_values(value.trace),
            },
        )
        _write_versions(
            self._session,
            schema.governance_decision_policies,
            "governance_decision_id",
            id_value(value.governance_decision_id),
            value.policy_versions,
        )

    def get(self, value_id: Any) -> GovernanceDecision | None:
        row = _one(
            self._session,
            select(schema.governance_decisions).where(
                schema.governance_decisions.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import GovernanceDecisionId, OrganizationId
        from aeos.governance.domain import GovernanceDecisionResult

        evaluated = (
            None
            if row["evaluated_actor_id"] is None
            else actor_from_values(
                row["evaluated_actor_id"],
                row["evaluated_actor_type"],
                row["evaluated_actor_kind"],
            )
        )
        return GovernanceDecision(
            GovernanceDecisionId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            GovernanceDecisionResult(row["result"]),
            row["reason"],
            VersionRef(row["constitution_subject"], row["constitution_version"]),
            _versions(
                self._session,
                schema.governance_decision_policies,
                "governance_decision_id",
                row["id"],
            ),
            trace_from_values(row),
            row["decided_at"],
            evaluated,
        )


class ApprovalDecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: ApprovalDecision) -> None:
        constitution = value.constitution_version
        decided_by = actor_values(value.decided_by)
        _insert(
            self._session,
            schema.approval_decisions,
            {
                "id": id_value(value.approval_decision_id),
                "approval_request_id": id_value(value.approval_request_id),
                "organization_id": id_value(value.organization_id),
                "decision": value.decision.value,
                "decided_by_id": decided_by[0],
                "decided_by_type": decided_by[1],
                "decided_by_kind": decided_by[2],
                "reason": value.reason,
                "decided_at": value.decided_at,
                "constitution_subject": None
                if constitution is None
                else constitution.subject,
                "constitution_version": None
                if constitution is None
                else constitution.version,
                **trace_values(value.trace),
            },
        )
        _write_versions(
            self._session,
            schema.approval_decision_policies,
            "approval_decision_id",
            id_value(value.approval_decision_id),
            value.policy_versions,
        )

    def get(self, value_id: Any) -> ApprovalDecision | None:
        row = _one(
            self._session,
            select(schema.approval_decisions).where(
                schema.approval_decisions.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import ApprovalDecisionId, ApprovalRequestId, OrganizationId
        from aeos.governance.domain import ApprovalDecisionResult

        constitution = (
            None
            if row["constitution_subject"] is None
            else VersionRef(row["constitution_subject"], row["constitution_version"])
        )
        return ApprovalDecision(
            ApprovalDecisionId.from_string(row["id"]),
            ApprovalRequestId.from_string(row["approval_request_id"]),
            OrganizationId.from_string(row["organization_id"]),
            ApprovalDecisionResult(row["decision"]),
            actor_from_values(
                row["decided_by_id"], row["decided_by_type"], row["decided_by_kind"]
            ),
            row["reason"],
            row["decided_at"],
            constitution,
            _versions(
                self._session,
                schema.approval_decision_policies,
                "approval_decision_id",
                row["id"],
            ),
            trace_from_values(row),
        )


class ApprovalRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: ApprovalRequest) -> None:
        requester = actor_values(value.requester)
        constitution = value.constitution_version
        _insert(
            self._session,
            schema.approval_requests,
            {
                "id": id_value(value.approval_request_id),
                "organization_id": id_value(value.organization_id),
                "requester_id": requester[0],
                "requester_type": requester[1],
                "requester_kind": requester[2],
                "capability": value.capability.value,
                "reason": value.reason,
                "requested_at": value.requested_at,
                "expires_at": value.expires_at,
                "constitution_subject": None
                if constitution is None
                else constitution.subject,
                "constitution_version": None
                if constitution is None
                else constitution.version,
                "governance_decision_id": None
                if value.governance_decision_id is None
                else id_value(value.governance_decision_id),
                "required_role_id": None
                if value.required_role_id is None
                else id_value(value.required_role_id),
                "state": value.state.value,
                **trace_values(value.trace),
            },
        )
        _write_versions(
            self._session,
            schema.approval_request_policies,
            "approval_request_id",
            id_value(value.approval_request_id),
            value.policy_versions,
        )

    def get(self, value_id: Any) -> ApprovalRequest | None:
        row = _one(
            self._session,
            select(schema.approval_requests).where(
                schema.approval_requests.c.id == id_value(value_id)
            ),
        )
        if row is None:
            return None
        from aeos.core import (
            ApprovalRequestId,
            GovernanceDecisionId,
            OrganizationId,
            RoleId,
        )

        request = ApprovalRequest(
            ApprovalRequestId.from_string(row["id"]),
            OrganizationId.from_string(row["organization_id"]),
            actor_from_values(
                row["requester_id"], row["requester_type"], row["requester_kind"]
            ),
            PermissionCapability(row["capability"]),
            row["reason"],
            row["requested_at"],
            row["expires_at"],
            None
            if row["constitution_subject"] is None
            else VersionRef(row["constitution_subject"], row["constitution_version"]),
            _versions(
                self._session,
                schema.approval_request_policies,
                "approval_request_id",
                row["id"],
            ),
            None
            if row["governance_decision_id"] is None
            else GovernanceDecisionId.from_string(row["governance_decision_id"]),
            None
            if row["required_role_id"] is None
            else RoleId.from_string(row["required_role_id"]),
            trace_from_values(row),
        )
        from aeos.governance.domain import ApprovalRequestState

        state = ApprovalRequestState(row["state"])
        if state is ApprovalRequestState.PENDING:
            return request
        if state is ApprovalRequestState.CANCELLED:
            request.cancel()
            return request
        if state is ApprovalRequestState.EXPIRED:
            if request.expires_at is None:
                raise ValueError("expired request lacks expires_at")
            request.expire(request.expires_at)
            return request
        persisted_decision_ids = cast(
            Sequence[str],
            self._session.execute(
                select(schema.approval_decisions.c.id).where(
                    schema.approval_decisions.c.approval_request_id == row["id"]
                )
            )
            .scalars()
            .all(),
        )
        decisions: Sequence[ApprovalDecisionId] = tuple(
            ApprovalDecisionId.from_string(persisted_id)
            for persisted_id in persisted_decision_ids
        )
        if len(decisions) != 1:
            raise ValueError("decided request must have exactly one decision")
        decision = ApprovalDecisionRepository(self._session).get(decisions[0])
        if decision is None:
            raise ValueError("approval decision row disappeared")
        request.record_decision(decision)
        return request


__all__ = [
    "ApprovalDecisionRepository",
    "ApprovalRequestRepository",
    "GovernanceDecisionRepository",
    "PermissionGrantRepository",
]
