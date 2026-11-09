"""Local tenant-partitioned adapters for existing LIVE JSON stores."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping, cast

from aeos.core.ids import OrganizationId
from aeos.live.adapters.opportunity_inbox import LocalOpportunityInbox
from aeos.live.adapters.opportunity_pipeline import LocalOpportunityPipeline
from aeos.live.domain.opportunity_activation import PipelineRecord
from aeos.live.domain.opportunity_inbox import OpportunityRecord
from aeos.live.domain.errors import InvalidLiveContract
from aeos.live.domain.profile import parse_business_profile_document
from aeos.tenancy.domain import TenantContext
from aeos.tenancy.ports import TenantDataCollection


class LocalTenantDataRepository:
    """Store JSON envelopes below a tenant-derived, non-user-selectable path."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def get(
        self, context: TenantContext, collection: TenantDataCollection, record_id: str
    ) -> object | None:
        path = self._record_path(context, collection, record_id)
        if not path.exists():
            return None
        if path.is_symlink():
            raise InvalidLiveContract("tenant record path cannot be a symbolic link")
        envelope = self._read(path)
        if (
            envelope.get("organization_id") != context.organization_id.value
            or envelope.get("record_id") != record_id
        ):
            raise InvalidLiveContract("stored tenant data has mismatched ownership")
        payload = envelope.get("data")
        _validate_payload_owner(payload, context.organization_id.value)
        return payload

    def list(
        self, context: TenantContext, collection: TenantDataCollection
    ) -> tuple[tuple[str, object], ...]:
        directory = self._collection_path(context, collection)
        if not directory.exists():
            return ()
        records: list[tuple[str, object]] = []
        for path in sorted(directory.glob("*.json")):
            if path.is_symlink():
                raise InvalidLiveContract(
                    "tenant record path cannot be a symbolic link"
                )
            envelope = self._read(path)
            record_id = envelope.get("record_id")
            if envelope.get("organization_id") != context.organization_id.value:
                raise InvalidLiveContract("stored tenant data has mismatched ownership")
            if not isinstance(record_id, str) or not record_id.strip():
                raise InvalidLiveContract("stored tenant record ID is missing")
            payload = envelope.get("data")
            _validate_payload_owner(payload, context.organization_id.value)
            records.append((record_id, payload))
        return tuple(records)

    def add(
        self,
        context: TenantContext,
        collection: TenantDataCollection,
        record_id: str,
        payload: object,
    ) -> None:
        path = self._record_path(context, collection, record_id)
        _validate_payload_owner(payload, context.organization_id.value)
        encoded = self._encode_envelope(context, record_id, payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._validate_local_path(path)
        descriptor: int | None = None
        created = False
        try:
            descriptor = os.open(
                path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            created = True
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as record:
                descriptor = None
                record.write(encoded)
                record.write("\n")
                record.flush()
                os.fsync(record.fileno())
        except Exception:
            if descriptor is not None:
                os.close(descriptor)
            if created and path.exists() and path.is_file():
                path.unlink()
            raise

    def put(
        self,
        context: TenantContext,
        collection: TenantDataCollection,
        record_id: str,
        payload: object,
    ) -> None:
        path = self._record_path(context, collection, record_id)
        _validate_payload_owner(payload, context.organization_id.value)
        encoded = self._encode_envelope(context, record_id, payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._validate_local_path(path)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=path.parent,
                prefix=".tenant-record-",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = temporary.name
                temporary.write(encoded)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def delete(
        self, context: TenantContext, collection: TenantDataCollection, record_id: str
    ) -> bool:
        if not isinstance(context, TenantContext) or not context.is_active():
            raise InvalidLiveContract("tenant data requires an active TenantContext")
        if not context.role.can_manage_profiles:
            raise InvalidLiveContract("tenant administrator role is required to delete")
        path = self._record_path(context, collection, record_id)
        if not path.exists():
            return False
        if path.is_symlink():
            raise InvalidLiveContract("tenant record path cannot be a symbolic link")
        envelope = self._read(path)
        if (
            envelope.get("organization_id") != context.organization_id.value
            or envelope.get("record_id") != record_id
        ):
            raise InvalidLiveContract("stored tenant data has mismatched ownership")
        path.unlink()
        return True

    def opportunity_inbox(self, context: TenantContext) -> TenantScopedOpportunityInbox:
        self._validate_context(context)
        return TenantScopedOpportunityInbox(
            context,
            LocalOpportunityInbox(
                self._collection_path(context, TenantDataCollection.OPPORTUNITY_INBOX)
                / "typed"
                / "store.json",
                organization_id=context.organization_id,
            ),
        )

    def opportunity_pipeline(
        self, context: TenantContext
    ) -> TenantScopedOpportunityPipeline:
        self._validate_context(context)
        return TenantScopedOpportunityPipeline(
            context,
            LocalOpportunityPipeline(
                self._collection_path(context, TenantDataCollection.FOLLOW_UP_HISTORY)
                / "typed"
                / "store.json",
                organization_id=context.organization_id,
            ),
        )

    def _record_path(
        self, context: TenantContext, collection: TenantDataCollection, record_id: str
    ) -> Path:
        if not isinstance(context, TenantContext):
            raise InvalidLiveContract("tenant data requires a resolved TenantContext")
        if not isinstance(collection, TenantDataCollection):
            raise InvalidLiveContract("collection must be a TenantDataCollection")
        if not isinstance(record_id, str) or not record_id.strip():
            raise InvalidLiveContract("tenant record ID must be non-blank")
        key = hashlib.sha256(record_id.encode("utf-8")).hexdigest()
        path = self._collection_path(context, collection) / f"{key}.json"
        self._validate_local_path(path)
        return path

    def _collection_path(
        self, context: TenantContext, collection: TenantDataCollection
    ) -> Path:
        if not isinstance(context, TenantContext):
            raise InvalidLiveContract("tenant data requires a resolved TenantContext")
        if not context.is_active():
            raise InvalidLiveContract("tenant context is no longer authorized")
        if not isinstance(collection, TenantDataCollection):
            raise InvalidLiveContract("collection must be a TenantDataCollection")
        organization_key = hashlib.sha256(
            context.organization_id.value.encode("utf-8")
        ).hexdigest()
        root = self.root.resolve()
        path = root / f"org-{organization_key}" / collection.value
        self._validate_local_path(path)
        return path

    def _encode_envelope(
        self, context: TenantContext, record_id: str, payload: object
    ) -> str:
        try:
            return json.dumps(
                {
                    "organization_id": context.organization_id.value,
                    "record_id": record_id,
                    "data": payload,
                },
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
        except (TypeError, ValueError) as error:
            raise InvalidLiveContract(
                f"tenant data must be JSON-compatible: {error}"
            ) from error

    @staticmethod
    def _validate_context(context: TenantContext) -> None:
        if not isinstance(context, TenantContext) or not context.is_active():
            raise InvalidLiveContract("tenant data requires an active TenantContext")

    @staticmethod
    def _validate_local_path(path: Path) -> None:
        try:
            if path.resolve(strict=False) != path:
                raise InvalidLiveContract(
                    "tenant storage paths cannot follow symbolic links"
                )
        except (OSError, RuntimeError) as error:
            raise InvalidLiveContract("tenant storage path is invalid") from error

    @staticmethod
    def _read(path: Path) -> dict[str, object]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise InvalidLiveContract(f"could not read tenant data: {error}") from error
        if not isinstance(value, dict):
            raise InvalidLiveContract("tenant data envelope must be an object")
        return cast(dict[str, object], value)


class TenantScopedOpportunityInbox:
    """Tenant boundary around the validated inbox domain adapter."""

    def __init__(self, context: TenantContext, store: LocalOpportunityInbox) -> None:
        self._context = context
        self._store = store

    def list_records(self) -> tuple[OpportunityRecord, ...]:
        self._authorize()
        return self._store.list_records()

    def get(self, opportunity_id: str) -> OpportunityRecord | None:
        self._authorize()
        return self._store.get(opportunity_id)

    def find_duplicate(self, record: OpportunityRecord) -> OpportunityRecord | None:
        self._authorize()
        return self._store.find_duplicate(record)

    def add(
        self,
        record: OpportunityRecord,
        *,
        attested_evidence_ids: tuple[str, ...],
    ) -> tuple[OpportunityRecord, bool]:
        """Persist only source evidence attested by this tenant manager."""

        self._authorize(write=True)
        return self._store.add(
            record,
            operator_context=self._context,
            attested_evidence_ids=attested_evidence_ids,
        )

    def put(self, record: OpportunityRecord) -> None:
        self._authorize(write=True)
        self._store.put(record)

    def put_many(self, records: tuple[OpportunityRecord, ...]) -> None:
        self._authorize(write=True)
        self._store.put_many(records)

    def audit_history(self) -> dict[str, tuple[str, ...]]:
        self._authorize()
        return self._store.audit_history()

    def _authorize(self, *, write: bool = False) -> None:
        if not self._context.is_active():
            raise InvalidLiveContract("tenant membership is no longer active")
        if write and not self._context.role.can_manage_profiles:
            raise InvalidLiveContract("tenant administrator role is required to write")


class TenantScopedOpportunityPipeline:
    """Tenant boundary around the validated follow-up history adapter."""

    def __init__(self, context: TenantContext, store: LocalOpportunityPipeline) -> None:
        self._context = context
        self._store = store

    def list_records(self) -> tuple[PipelineRecord, ...]:
        self._authorize()
        return self._store.list_records()

    def get(self, prospect_id: str) -> PipelineRecord | None:
        self._authorize()
        return self._store.get(prospect_id)

    def put(self, record: PipelineRecord) -> None:
        self._authorize(write=True)
        self._store.put(record)

    def ensure(self, record: PipelineRecord) -> PipelineRecord:
        self._authorize(write=True)
        return self._store.ensure(record)

    def _authorize(self, *, write: bool = False) -> None:
        if not self._context.is_active():
            raise InvalidLiveContract("tenant membership is no longer active")
        if write and not self._context.role.can_manage_profiles:
            raise InvalidLiveContract("tenant administrator role is required to write")


class LocalTenantFileReferenceRepository:
    """Read canonical seed files without copying them into tenant storage."""

    def __init__(
        self,
        root: str | Path,
        references: Mapping[OrganizationId, Mapping[TenantDataCollection, str | Path]],
        profile_references: Mapping[OrganizationId, str | Path] | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        private_path_owners: dict[Path, OrganizationId] = {}
        public_source_paths: set[Path] = set()
        self.profile_references: dict[OrganizationId, Path] = {}
        for organization_id, reference in (profile_references or {}).items():
            path = _validated_reference_path(
                self.root, reference, "tenant profile reference"
            )
            prior_owner = private_path_owners.get(path)
            if prior_owner not in (None, organization_id):
                raise InvalidLiveContract(
                    "private profile files cannot be shared across organizations"
                )
            private_path_owners[path] = organization_id
            self.profile_references[organization_id] = path

        self.references: dict[OrganizationId, dict[TenantDataCollection, Path]] = {}
        for organization_id, configured in references.items():
            tenant_references: dict[TenantDataCollection, Path] = {}
            for collection, reference in configured.items():
                path = _validated_reference_path(
                    self.root, reference, "tenant data reference"
                )
                if collection is TenantDataCollection.PUBLIC_MARKET_SOURCES:
                    if path in private_path_owners and (
                        private_path_owners[path] != organization_id
                    ):
                        raise InvalidLiveContract(
                            "public sources cannot alias another organization's private file"
                        )
                    public_source_paths.add(path)
                else:
                    if path in public_source_paths:
                        raise InvalidLiveContract(
                            "private tenant data cannot reuse a public source file"
                        )
                    prior_owner = private_path_owners.get(path)
                    if prior_owner not in (None, organization_id):
                        raise InvalidLiveContract(
                            "private data files cannot be shared across organizations"
                        )
                    private_path_owners[path] = organization_id
                tenant_references[collection] = path
            self.references[organization_id] = tenant_references

    @classmethod
    def from_manifest_files(
        cls,
        root: str | Path,
        manifests: Mapping[OrganizationId, str | Path],
    ) -> LocalTenantFileReferenceRepository:
        root_path = Path(root).resolve()
        references: dict[OrganizationId, dict[TenantDataCollection, str | Path]] = {}
        profile_references: dict[OrganizationId, str | Path] = {}
        for organization_id, manifest_ref in manifests.items():
            manifest_path = _validated_reference_path(
                root_path, manifest_ref, "tenant manifest"
            )
            try:
                manifest: object = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise InvalidLiveContract(
                    f"could not read tenant manifest: {error}"
                ) from error
            if not isinstance(manifest, dict):
                raise InvalidLiveContract("tenant manifest must be an object")
            if manifest.get("organization_id") != organization_id.value:
                raise InvalidLiveContract(
                    "tenant manifest organization_id does not match its registry key"
                )
            raw_files = manifest.get("shared_data_files", {})
            if not isinstance(raw_files, dict):
                raise InvalidLiveContract("shared_data_files must be an object")
            raw_profile = manifest.get("profile_file")
            if not isinstance(raw_profile, str) or not raw_profile.strip():
                raise InvalidLiveContract("profile_file must be a non-blank string")
            profile_candidate = manifest_path.parent / raw_profile
            profile_path = _validated_reference_path(
                root_path, profile_candidate, "tenant profile reference"
            )
            profile_references[organization_id] = profile_path
            tenant_references: dict[TenantDataCollection, str | Path] = {}
            for raw_collection, raw_path in raw_files.items():
                try:
                    collection = TenantDataCollection(raw_collection)
                except ValueError as error:
                    raise InvalidLiveContract(
                        f"unsupported tenant data collection: {raw_collection}"
                    ) from error
                if not isinstance(raw_path, str) or not raw_path.strip():
                    raise InvalidLiveContract(
                        "tenant data reference paths must be non-blank strings"
                    )
                reference_candidate = manifest_path.parent / raw_path
                reference_path = _validated_reference_path(
                    root_path, reference_candidate, "tenant data reference"
                )
                tenant_references[collection] = reference_path
            references[organization_id] = tenant_references
        return cls(root_path, references, profile_references)

    def read_profile(self, context: TenantContext) -> object | None:
        if not isinstance(context, TenantContext) or not context.is_active():
            raise InvalidLiveContract(
                "profile references require an active TenantContext"
            )
        configured = self.profile_references.get(context.organization_id)
        if configured is None:
            return None
        path = _validated_reference_path(
            self.root, configured, "tenant profile reference"
        )
        try:
            payload: object = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise InvalidLiveContract(
                f"could not read tenant profile reference: {error}"
            ) from error
        if not isinstance(payload, dict):
            raise InvalidLiveContract("tenant profile must be a JSON object")
        _validate_payload_owner(payload, context.organization_id.value)
        profile = parse_business_profile_document(cast(dict[str, object], payload))
        return {
            **profile.to_dict(),
            "organization_id": context.organization_id.value,
        }

    def read_reference(
        self, context: TenantContext, collection: TenantDataCollection
    ) -> object | None:
        if not isinstance(context, TenantContext):
            raise InvalidLiveContract(
                "file references require a resolved TenantContext"
            )
        if not context.is_active():
            raise InvalidLiveContract("tenant context is no longer authorized")
        if not isinstance(collection, TenantDataCollection):
            raise InvalidLiveContract("collection must be a TenantDataCollection")
        configured = self.references.get(context.organization_id)
        if configured is None or collection not in configured:
            return None
        path = _validated_reference_path(
            self.root, configured[collection], "tenant data reference"
        )
        try:
            payload: object = json.loads(path.read_text(encoding="utf-8"))
            _validate_payload_owner(payload, context.organization_id.value)
            return {
                "organization_id": context.organization_id.value,
                "data": payload,
            }
        except (OSError, json.JSONDecodeError) as error:
            raise InvalidLiveContract(
                f"could not read tenant file reference: {error}"
            ) from error


__all__ = ["LocalTenantDataRepository", "LocalTenantFileReferenceRepository"]


def _validated_reference_path(root: Path, value: str | Path, label: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    lexical_path = Path(os.path.abspath(candidate))
    try:
        resolved_path = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise InvalidLiveContract(f"{label} path is invalid") from error
    if not lexical_path.is_relative_to(root) or not resolved_path.is_relative_to(root):
        raise InvalidLiveContract(f"{label} escapes its trusted root")
    if resolved_path != lexical_path:
        raise InvalidLiveContract(f"{label} cannot follow symbolic links")
    return resolved_path


def _validate_payload_owner(payload: object, organization_id: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if key in {"organization_id", "owner_organization_id", "tenant_id"}:
                if value is not None and value != organization_id:
                    raise InvalidLiveContract(
                        "record organization_id owner must match the authorized tenant"
                    )
            _validate_payload_owner(value, organization_id)
    elif isinstance(payload, list | tuple):
        for value in payload:
            _validate_payload_owner(value, organization_id)
