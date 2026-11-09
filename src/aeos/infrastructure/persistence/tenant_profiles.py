"""SQLAlchemy adapter for tenant-owned business profiles."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from aeos.infrastructure.persistence import schema
from aeos.live.domain.profile import BusinessProfile
from aeos.tenancy.domain import TenantContext
from aeos.tenancy.errors import BusinessProfileNotFound, TenantAccessDenied


class BusinessProfileRepository:
    """Persist the existing profile contract under its validated tenant ID."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, context: TenantContext, profile: BusinessProfile) -> None:
        self._validate_scope(context, profile)
        self._set_database_scope(context)
        self._session.execute(
            schema.organization_business_profiles.insert().values(
                organization_id=context.organization_id.value,
                profile_data=profile.to_dict(),
            )
        )

    def get(self, context: TenantContext) -> BusinessProfile | None:
        self._validate_context(context)
        self._set_database_scope(context)
        row = self._session.execute(
            select(schema.organization_business_profiles.c.profile_data).where(
                schema.organization_business_profiles.c.organization_id
                == context.organization_id.value
            )
        ).first()
        if row is None:
            return None
        payload: Any = row[0]
        if not isinstance(payload, dict):
            raise ValueError("stored business profile must be a JSON object")
        profile = BusinessProfile.from_dict(payload)
        if profile.organization_id != context.organization_id:
            raise TenantAccessDenied()
        return profile

    def update(self, context: TenantContext, profile: BusinessProfile) -> None:
        self._validate_scope(context, profile)
        self._set_database_scope(context)
        result = self._session.execute(
            update(schema.organization_business_profiles)
            .where(
                schema.organization_business_profiles.c.organization_id
                == context.organization_id.value
            )
            .values(profile_data=profile.to_dict())
        )
        if int(getattr(result, "rowcount", -1)) != 1:
            raise BusinessProfileNotFound()

    @staticmethod
    def _validate_scope(context: TenantContext, profile: BusinessProfile) -> None:
        if not isinstance(context, TenantContext) or not isinstance(
            profile, BusinessProfile
        ):
            raise TenantAccessDenied()
        BusinessProfileRepository._validate_context(context)
        if not context.role.can_manage_profiles:
            raise TenantAccessDenied()
        if profile.organization_id != context.organization_id:
            raise TenantAccessDenied()

    @staticmethod
    def _validate_context(context: TenantContext) -> None:
        if not isinstance(context, TenantContext) or not context.is_active():
            raise TenantAccessDenied()

    def _set_database_scope(self, context: TenantContext) -> None:
        if self._session.get_bind().dialect.name == "postgresql":
            self._session.execute(
                select(
                    func.set_config(
                        "aeos.organization_id", context.organization_id.value, True
                    )
                )
            )
