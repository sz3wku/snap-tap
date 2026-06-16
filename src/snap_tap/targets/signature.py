from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from snap_tap.semantics import SemanticRole
from snap_tap.snapshots import SnapshotArtifactRef, SnapshotBounds
from snap_tap.targets.models import (
    SNAPSHOT_TARGETS_SCHEMA_VERSION,
    TARGET_SIGNATURE_SCHEMA_VERSION,
    SnapshotTarget,
    SnapshotTargets,
    TargetSignature,
    TargetSignatureError,
    TargetSignatureRequirements,
)

__all__ = [
    "TargetSignatureError",
    "build_target_signature",
    "target_signature_to_dict",
]

_ALLOWED_REF_NAMES = frozenset({"xml", "screenshot", "manifest"})


def build_target_signature(
    snapshot_targets: SnapshotTargets,
    display_id: str,
) -> TargetSignature:
    if snapshot_targets.schema_version != SNAPSHOT_TARGETS_SCHEMA_VERSION:
        raise TargetSignatureError(
            code="target_signature_unsupported_version",
            detail="Target signatures require snapshot_targets.v1 input.",
        )
    _validate_source_identity(snapshot_targets)
    requested_display_id = _required_text(display_id, "display_id")

    target = _target_by_display_id(snapshot_targets, requested_display_id)
    if target.snapshot_id != snapshot_targets.snapshot_id:
        raise TargetSignatureError(
            code="target_signature_invalid",
            detail="Source target snapshot id does not match snapshot_targets.",
        )
    _validate_target_fields(target)

    identity = _identity(target)
    if not identity:
        raise TargetSignatureError(
            code="target_signature_insufficient_identity",
            detail="Target signature requires non-coordinate identity facts.",
        )
    refs = _validated_refs(snapshot_targets.refs)

    return TargetSignature(
        schema_version=TARGET_SIGNATURE_SCHEMA_VERSION,
        signature_id=_signature_id(
            source=snapshot_targets,
            target=target,
            identity=identity,
        ),
        source_snapshot_id=snapshot_targets.snapshot_id,
        device_id=snapshot_targets.device_id,
        captured_at=snapshot_targets.captured_at,
        display_id=target.display_id,
        semantic_index=target.semantic_index,
        source_index=target.source_index,
        role=target.role,
        identity=identity,
        source_bounds=target.bounds,
        requirements=TargetSignatureRequirements(),
        identity_strength=_identity_strength(identity),
        refs=refs,
    )


def target_signature_to_dict(signature: TargetSignature) -> dict[str, object]:
    return {
        "schema_version": signature.schema_version,
        "signature_id": signature.signature_id,
        "source_snapshot_id": signature.source_snapshot_id,
        "device_id": signature.device_id,
        "captured_at": signature.captured_at,
        "display_id": signature.display_id,
        "semantic_index": signature.semantic_index,
        "source_index": signature.source_index,
        "role": signature.role.value,
        "identity": dict(signature.identity),
        "source_bounds": _snapshot_bounds_to_dict(signature.source_bounds),
        "requirements": _requirements_to_dict(signature.requirements),
        "identity_strength": signature.identity_strength,
        "refs": {
            name: _snapshot_artifact_ref_to_dict(name, ref)
            for name, ref in _validated_refs(signature.refs).items()
        },
    }


def _validate_source_identity(snapshot_targets: SnapshotTargets) -> None:
    _required_text(snapshot_targets.snapshot_id, "snapshot_id")
    _required_text(snapshot_targets.device_id, "device_id")
    _required_text(snapshot_targets.captured_at, "captured_at")


def _target_by_display_id(
    snapshot_targets: SnapshotTargets,
    display_id: str,
) -> SnapshotTarget:
    by_display_id: dict[str, SnapshotTarget] = {}
    for target in snapshot_targets.targets:
        target_display_id = _required_text(target.display_id, "target.display_id")
        if target_display_id in by_display_id:
            raise TargetSignatureError(
                code="target_signature_duplicate_display_id",
                detail="Snapshot-local display id maps to multiple targets.",
            )
        by_display_id[target_display_id] = target

    selected = by_display_id.get(display_id)
    if selected is None:
        raise TargetSignatureError(
            code="target_signature_missing",
            detail="Requested display id is absent from snapshot_targets.",
        )
    return selected


def _validate_target_fields(target: SnapshotTarget) -> None:
    _required_text(target.snapshot_id, "target.snapshot_id")
    _required_text(target.display_id, "target.display_id")
    _required_int(target.semantic_index, "target.semantic_index")
    _required_int(target.source_index, "target.source_index")
    if not isinstance(target.role, SemanticRole):
        raise TargetSignatureError(
            code="target_signature_invalid",
            detail="Target role must be a semantic role.",
        )
    if not isinstance(target.bounds, SnapshotBounds):
        raise TargetSignatureError(
            code="target_signature_invalid",
            detail="Target source bounds are invalid.",
        )


def _identity(target: SnapshotTarget) -> dict[str, str]:
    identity: dict[str, str] = {}
    if target.label is not None:
        identity["label"] = _required_text(target.label, "target.label")
        identity["label_source"] = _required_text(
            target.label_source,
            "target.label_source",
        )
    if target.resource_id is not None:
        identity["resource_id"] = _required_text(
            target.resource_id,
            "target.resource_id",
        )
    if target.class_name is not None:
        identity["class_name"] = _required_text(
            target.class_name,
            "target.class_name",
        )
    if target.package is not None:
        identity["package"] = _required_text(target.package, "target.package")
    if target.role is not SemanticRole.UNKNOWN:
        identity["role"] = target.role.value
    return identity


def _identity_strength(identity: Mapping[str, str]) -> str:
    if "resource_id" in identity:
        return "strong"
    if "label" in identity or {"class_name", "package"} <= set(identity):
        return "medium"
    return "weak"


def _validated_refs(
    refs: Mapping[str, SnapshotArtifactRef],
) -> dict[str, SnapshotArtifactRef]:
    validated: dict[str, SnapshotArtifactRef] = {}
    for name, ref in refs.items():
        if name not in _ALLOWED_REF_NAMES:
            raise TargetSignatureError(
                code="target_signature_invalid",
                detail="Target signature source refs contain unsupported ref names.",
            )
        validated[name] = ref
    return validated


def _signature_id(
    *,
    source: SnapshotTargets,
    target: SnapshotTarget,
    identity: Mapping[str, str],
) -> str:
    payload: dict[str, object] = {
        "schema_version": TARGET_SIGNATURE_SCHEMA_VERSION,
        "source_snapshot_id": source.snapshot_id,
        "device_id": source.device_id,
        "captured_at": source.captured_at,
        "display_id": target.display_id,
        "semantic_index": target.semantic_index,
        "source_index": target.source_index,
        "role": target.role.value,
        "identity": dict(sorted(identity.items())),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"target_signature:{hashlib.sha256(canonical).hexdigest()}"


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TargetSignatureError(
            code="target_signature_invalid",
            detail=f"{field_name} must be text.",
        )
    normalized = value.strip()
    if not normalized:
        raise TargetSignatureError(
            code="target_signature_invalid",
            detail=f"{field_name} must not be empty.",
        )
    if normalized != value:
        raise TargetSignatureError(
            code="target_signature_invalid",
            detail=f"{field_name} must already be normalized.",
        )
    return normalized


def _required_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TargetSignatureError(
            code="target_signature_invalid",
            detail=f"{field_name} must be a non-negative integer.",
        )
    return value


def _snapshot_bounds_to_dict(bounds: SnapshotBounds) -> dict[str, object]:
    return {
        "left": bounds.left,
        "top": bounds.top,
        "right": bounds.right,
        "bottom": bounds.bottom,
        "width": bounds.width,
        "height": bounds.height,
        "center_x": bounds.center_x,
        "center_y": bounds.center_y,
    }


def _requirements_to_dict(
    requirements: TargetSignatureRequirements,
) -> dict[str, object]:
    return {
        "requires_fresh_snapshot": requirements.requires_fresh_snapshot,
        "requires_resolution": requirements.requires_resolution,
        "not_executable_directly": requirements.not_executable_directly,
    }


def _snapshot_artifact_ref_to_dict(
    name: str,
    ref: SnapshotArtifactRef,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "path": ref.path,
        "sha256": ref.sha256,
        "byte_length": ref.byte_length,
    }
    metadata = dict(ref.metadata)
    if name == "xml":
        node_count = metadata.get("node_count")
        if isinstance(node_count, int) and not isinstance(node_count, bool):
            payload["node_count"] = node_count
    elif name == "screenshot":
        image_format = metadata.get("format")
        if isinstance(image_format, str):
            payload["format"] = image_format
        for key in ("width", "height"):
            value = metadata.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                payload[key] = value
    elif name == "manifest":
        schema_version = metadata.get("schema_version")
        if isinstance(schema_version, str):
            payload["metadata"] = {"schema_version": schema_version}
    return payload
