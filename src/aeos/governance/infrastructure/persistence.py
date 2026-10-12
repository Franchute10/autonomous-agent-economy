"""Governance-owned persistence adapter exports."""

from aeos.infrastructure.persistence.governance import (
    ApprovalDecisionRepository,
    ApprovalRequestRepository,
    GovernanceDecisionRepository,
    PermissionGrantRepository,
)
from aeos.infrastructure.persistence.repositories import (
    ConstitutionVersionRepository,
    PolicyVersionRepository,
)

__all__ = [
    "ApprovalDecisionRepository",
    "ApprovalRequestRepository",
    "ConstitutionVersionRepository",
    "GovernanceDecisionRepository",
    "PermissionGrantRepository",
    "PolicyVersionRepository",
]
