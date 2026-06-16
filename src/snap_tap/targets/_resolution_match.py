from __future__ import annotations

from collections.abc import Mapping

from snap_tap.semantics import (
    SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
    SemanticRole,
    SemanticSnapshot,
)
from snap_tap.snapshots import SnapshotBounds
from snap_tap.targets.models import (
    TARGET_SIGNATURE_SCHEMA_VERSION,
    SnapshotTarget,
    TargetSignature,
    TargetSignatureRequirements,
)


_IDENTITY_FIELD_ORDER = (
    "resource_id",
    "label",
    "label_source",
    "class_name",
    "package",
    "role",
)
_IDENTITY_FIELDS = frozenset(_IDENTITY_FIELD_ORDER)


class ResolutionBlocked(Exception):
    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def validated_signature_identity(signature: TargetSignature) -> dict[str, str]:
    if signature.schema_version != TARGET_SIGNATURE_SCHEMA_VERSION:
        raise ResolutionBlocked(
            code="target_resolution_invalid_signature",
            detail="Target resolution requires target_signature.v1 input.",
        )
    _required_text(
        signature.signature_id,
        "signature.signature_id",
        "target_resolution_invalid_signature",
    )
    _required_text(
        signature.source_snapshot_id,
        "signature.source_snapshot_id",
        "target_resolution_invalid_signature",
    )
    _required_text(
        signature.device_id,
        "signature.device_id",
        "target_resolution_invalid_signature",
    )
    _required_text(
        signature.captured_at,
        "signature.captured_at",
        "target_resolution_invalid_signature",
    )
    _required_text(
        signature.display_id,
        "signature.display_id",
        "target_resolution_invalid_signature",
    )
    _required_int(
        signature.semantic_index,
        "signature.semantic_index",
        "target_resolution_invalid_signature",
    )
    _required_int(
        signature.source_index,
        "signature.source_index",
        "target_resolution_invalid_signature",
    )
    if not isinstance(signature.role, SemanticRole):
        raise ResolutionBlocked(
            code="target_resolution_invalid_signature",
            detail="Target signature role must be a semantic role.",
        )
    if not isinstance(signature.source_bounds, SnapshotBounds):
        raise ResolutionBlocked(
            code="target_resolution_invalid_signature",
            detail="Target signature source bounds are invalid.",
        )
    _validate_requirements(signature.requirements)

    identity: dict[str, str] = {}
    if not isinstance(signature.identity, Mapping):
        raise ResolutionBlocked(
            code="target_resolution_invalid_signature",
            detail="Target signature identity must be a mapping.",
        )
    for key, value in signature.identity.items():
        if key not in _IDENTITY_FIELDS:
            raise ResolutionBlocked(
                code="target_resolution_invalid_signature",
                detail="Target signature contains unsupported identity fields.",
            )
        identity[key] = _required_text(
            value,
            f"signature.identity.{key}",
            "target_resolution_invalid_signature",
        )
    if "label" in identity and "label_source" not in identity:
        raise ResolutionBlocked(
            code="target_resolution_invalid_signature",
            detail="Label identity requires label_source.",
        )
    if "label_source" in identity and "label" not in identity:
        raise ResolutionBlocked(
            code="target_resolution_invalid_signature",
            detail="label_source identity is valid only with label.",
        )
    if "role" in identity:
        try:
            SemanticRole(identity["role"])
        except ValueError as exc:
            raise ResolutionBlocked(
                code="target_resolution_invalid_signature",
                detail="Target signature role identity is unsupported.",
            ) from exc
    if not identity:
        raise ResolutionBlocked(
            code="target_resolution_invalid_signature",
            detail="Target signature requires non-coordinate identity facts.",
        )
    return identity


def _validate_requirements(requirements: object) -> None:
    if not isinstance(requirements, TargetSignatureRequirements):
        raise ResolutionBlocked(
            code="target_resolution_invalid_signature",
            detail="Target signature requirements are invalid.",
        )
    if (
        not requirements.requires_fresh_snapshot
        or not requirements.requires_resolution
        or not requirements.not_executable_directly
    ):
        raise ResolutionBlocked(
            code="target_resolution_invalid_signature",
            detail="Target signature safety requirements must be true.",
        )


def validate_snapshot_identity(snapshot: SemanticSnapshot) -> None:
    if snapshot.schema_version != SEMANTIC_SNAPSHOT_SCHEMA_VERSION:
        raise ResolutionBlocked(
            code="target_resolution_invalid_snapshot",
            detail="Target resolution requires semantic_snapshot.v1 input.",
        )
    _required_text(
        snapshot.snapshot_id,
        "fresh_snapshot.snapshot_id",
        "target_resolution_invalid_snapshot",
    )
    _required_text(
        snapshot.device_id,
        "fresh_snapshot.device_id",
        "target_resolution_invalid_snapshot",
    )
    _required_text(
        snapshot.captured_at,
        "fresh_snapshot.captured_at",
        "target_resolution_invalid_snapshot",
    )


def target_matches(identity: Mapping[str, str], target: SnapshotTarget) -> bool:
    return all(
        _target_identity_value(target, field) == value
        for field, value in identity.items()
    )


def matched_fields(identity: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(field for field in _IDENTITY_FIELD_ORDER if field in identity)


def _target_identity_value(target: SnapshotTarget, field: str) -> str | None:
    if field == "resource_id":
        return target.resource_id
    if field == "label":
        return target.label
    if field == "label_source":
        return target.label_source if target.label is not None else None
    if field == "class_name":
        return target.class_name
    if field == "package":
        return target.package
    if field == "role":
        return target.role.value
    return None


def _required_text(value: object, field_name: str, code: str) -> str:
    if not isinstance(value, str):
        raise ResolutionBlocked(
            code=code,
            detail=f"{field_name} must be text.",
        )
    normalized = value.strip()
    if not normalized:
        raise ResolutionBlocked(
            code=code,
            detail=f"{field_name} must not be empty.",
        )
    if normalized != value:
        raise ResolutionBlocked(
            code=code,
            detail=f"{field_name} must already be normalized.",
        )
    return normalized


def _required_int(value: object, field_name: str, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ResolutionBlocked(
            code=code,
            detail=f"{field_name} must be a non-negative integer.",
        )
    return value
