"""Governance persistence ports."""

from typing import Protocol

from aeos.governance.domain import ConstitutionVersion, PolicyVersion


class ConstitutionVersionRepository(Protocol):
    def add(self, value: ConstitutionVersion) -> None: ...
    def get(self, value_id: object) -> ConstitutionVersion | None: ...


class PolicyVersionRepository(Protocol):
    def add(self, value: PolicyVersion) -> None: ...
    def get(self, value_id: object) -> PolicyVersion | None: ...


__all__ = ["ConstitutionVersionRepository", "PolicyVersionRepository"]
