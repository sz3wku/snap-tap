from __future__ import annotations

from collections.abc import Mapping

from snap_tap.snapshots import SnapshotArtifactRef, SnapshotBounds
from snap_tap.targets.models import (
    SnapshotTarget,
    TargetResolution,
    TargetResolutionBlockingReason,
    TargetResolutionError,
    TargetResolutionMatch,
)

_ALLOWED_REF_NAMES = frozenset({"xml", "screenshot", "manifest"})


def target_resolution_to_dict(resolution: TargetResolution) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": resolution.schema_version,
        "ok": resolution.ok,
        "status": resolution.status,
        "signature_id": resolution.signature_id,
        "source_snapshot_id": resolution.source_snapshot_id,
        "resolved_snapshot_id": resolution.resolved_snapshot_id,
        "device_id": resolution.device_id,
        "match": _match_to_dict(resolution.match),
        "refs": {
            name: snapshot_artifact_ref_to_dict(name, ref)
            for name, ref in validated_resolution_refs(resolution.refs).items()
        },
    }
    if resolution.resolved_target is not None:
        payload["resolved_target"] = _resolved_target_to_dict(
            resolution.resolved_target,
        )
    if resolution.blocking_reason is not None:
        payload["blocking_reason"] = _blocking_reason_to_dict(
            resolution.blocking_reason,
        )
    return payload


def validated_resolution_refs(
    refs: Mapping[str, SnapshotArtifactRef],
) -> dict[str, SnapshotArtifactRef]:
    if not isinstance(refs, Mapping):
        raise TargetResolutionError(
            code="target_resolution_invalid_snapshot",
            detail="Target resolution fresh refs must be a mapping.",
        )
    validated: dict[str, SnapshotArtifactRef] = {}
    for name, ref in refs.items():
        if name not in _ALLOWED_REF_NAMES:
            raise TargetResolutionError(
                code="target_resolution_invalid_snapshot",
                detail="Target resolution fresh refs contain unsupported ref names.",
            )
        _validate_ref(ref)
        validated[name] = ref
    return validated


def snapshot_artifact_ref_to_dict(
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


def _match_to_dict(match: TargetResolutionMatch) -> dict[str, object]:
    return {
        "identity_strength": match.identity_strength,
        "matched_fields": list(match.matched_fields),
        "candidate_count": match.candidate_count,
    }


def _blocking_reason_to_dict(
    blocking_reason: TargetResolutionBlockingReason,
) -> dict[str, object]:
    return {
        "code": blocking_reason.code,
        "detail": blocking_reason.detail,
        "touched_phone": blocking_reason.touched_phone,
    }


def _resolved_target_to_dict(target: SnapshotTarget) -> dict[str, object]:
    return {
        "display_id": target.display_id,
        "snapshot_id": target.snapshot_id,
        "semantic_index": target.semantic_index,
        "source_index": target.source_index,
        "role": target.role.value,
        "bounds": _snapshot_bounds_to_dict(target.bounds),
        "enabled": target.enabled,
        "clickable": target.clickable,
        "scrollable": target.scrollable,
        "actionable": target.actionable,
    }


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


def _validate_ref(ref: object) -> SnapshotArtifactRef:
    if not isinstance(ref, SnapshotArtifactRef):
        raise TargetResolutionError(
            code="target_resolution_invalid_snapshot",
            detail="Target resolution fresh refs must be snapshot artifact refs.",
        )
    _required_text(ref.path, "ref.path")
    _required_text(ref.sha256, "ref.sha256")
    if not isinstance(ref.byte_length, int) or isinstance(ref.byte_length, bool):
        raise TargetResolutionError(
            code="target_resolution_invalid_snapshot",
            detail="ref.byte_length must be a non-negative integer.",
        )
    if ref.byte_length < 0:
        raise TargetResolutionError(
            code="target_resolution_invalid_snapshot",
            detail="ref.byte_length must be a non-negative integer.",
        )
    if not isinstance(ref.metadata, Mapping):
        raise TargetResolutionError(
            code="target_resolution_invalid_snapshot",
            detail="ref.metadata must be a mapping.",
        )
    return ref


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TargetResolutionError(
            code="target_resolution_invalid_snapshot",
            detail=f"{field_name} must be text.",
        )
    normalized = value.strip()
    if not normalized:
        raise TargetResolutionError(
            code="target_resolution_invalid_snapshot",
            detail=f"{field_name} must not be empty.",
        )
    if normalized != value:
        raise TargetResolutionError(
            code="target_resolution_invalid_snapshot",
            detail=f"{field_name} must already be normalized.",
        )
    return normalized
