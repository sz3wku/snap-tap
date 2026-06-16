from __future__ import annotations

from collections.abc import Mapping

from snap_tap.primitives.models import PrimitiveRequestError
from snap_tap.semantics import SemanticRole
from snap_tap.snapshots import SnapshotArtifactRef, SnapshotBounds
from snap_tap.targets import (
    TARGET_SIGNATURE_SCHEMA_VERSION,
    TargetSignature,
    TargetSignatureRequirements,
)


def target_signature_from_dict(payload: Mapping[str, object]) -> TargetSignature:
    if payload.get("schema_version") != TARGET_SIGNATURE_SCHEMA_VERSION:
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail="Target signature file must contain target_signature.v1.",
        )
    requirements = _requirements(payload.get("requirements", {}))
    return TargetSignature(
        schema_version=TARGET_SIGNATURE_SCHEMA_VERSION,
        signature_id=_text(payload.get("signature_id"), "signature_id"),
        source_snapshot_id=_text(
            payload.get("source_snapshot_id"),
            "source_snapshot_id",
        ),
        device_id=_text(payload.get("device_id"), "device_id"),
        captured_at=_text(payload.get("captured_at"), "captured_at"),
        display_id=_text(payload.get("display_id"), "display_id"),
        semantic_index=_int(payload.get("semantic_index"), "semantic_index"),
        source_index=_int(payload.get("source_index"), "source_index"),
        role=_role(payload.get("role")),
        identity=_identity(payload.get("identity")),
        source_bounds=_bounds(payload.get("source_bounds")),
        requirements=requirements,
        identity_strength=_text(payload.get("identity_strength"), "identity_strength"),
        refs=_refs(payload.get("refs", {})),
    )


def _requirements(value: object) -> TargetSignatureRequirements:
    if not isinstance(value, Mapping):
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail="Target signature requirements must be an object.",
        )
    return TargetSignatureRequirements(
        requires_fresh_snapshot=_bool(
            value.get("requires_fresh_snapshot", True),
            "requirements.requires_fresh_snapshot",
        ),
        requires_resolution=_bool(
            value.get("requires_resolution", True),
            "requirements.requires_resolution",
        ),
        not_executable_directly=_bool(
            value.get("not_executable_directly", True),
            "requirements.not_executable_directly",
        ),
    )


def _identity(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail="Target signature identity must be an object.",
        )
    identity: dict[str, str] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            raise PrimitiveRequestError(
                code="primitive_invalid_request",
                detail="Target signature identity keys must be text.",
            )
        identity[key] = _text(raw, f"identity.{key}")
    if not identity:
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail="Target signature identity must not be empty.",
        )
    return identity


def _bounds(value: object) -> SnapshotBounds:
    if not isinstance(value, Mapping):
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail="Target signature source_bounds must be an object.",
        )
    return SnapshotBounds(
        left=_int(value.get("left"), "source_bounds.left"),
        top=_int(value.get("top"), "source_bounds.top"),
        right=_int(value.get("right"), "source_bounds.right"),
        bottom=_int(value.get("bottom"), "source_bounds.bottom"),
        width=_int(value.get("width"), "source_bounds.width"),
        height=_int(value.get("height"), "source_bounds.height"),
        center_x=_number(value.get("center_x"), "source_bounds.center_x"),
        center_y=_number(value.get("center_y"), "source_bounds.center_y"),
    )


def _refs(value: object) -> dict[str, SnapshotArtifactRef]:
    if not isinstance(value, Mapping):
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail="Target signature refs must be an object.",
        )
    refs: dict[str, SnapshotArtifactRef] = {}
    for name, raw_ref in value.items():
        if name not in {"xml", "screenshot", "manifest"}:
            raise PrimitiveRequestError(
                code="primitive_invalid_request",
                detail="Target signature refs contain unsupported names.",
            )
        if not isinstance(name, str) or not isinstance(raw_ref, Mapping):
            raise PrimitiveRequestError(
                code="primitive_invalid_request",
                detail="Target signature refs must be objects.",
            )
        refs[name] = SnapshotArtifactRef(
            path=_text(raw_ref.get("path"), f"refs.{name}.path"),
            sha256=_text(raw_ref.get("sha256"), f"refs.{name}.sha256"),
            byte_length=_int(raw_ref.get("byte_length"), f"refs.{name}.byte_length"),
            metadata=_metadata(raw_ref.get("metadata", {})),
        )
    return refs


def _metadata(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(item, (str, int, float, bool)) or item is None
    }


def _role(value: object) -> SemanticRole:
    text = _text(value, "role")
    try:
        return SemanticRole(text)
    except ValueError as exc:
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail="Target signature role is unsupported.",
        ) from exc


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value.strip() != value:
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail=f"Target signature {field_name} must be normalized text.",
        )
    return value


def _int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail=f"Target signature {field_name} must be a non-negative integer.",
        )
    return value


def _number(value: object, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail=f"Target signature {field_name} must be a non-negative number.",
        )
    return float(value)


def _bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail=f"Target signature {field_name} must be a boolean.",
        )
    return value
