from __future__ import annotations

from collections.abc import Mapping

from snap_tap.semantics import SEMANTIC_SNAPSHOT_SCHEMA_VERSION, SemanticElement
from snap_tap.semantics import SemanticRole, SemanticSnapshot
from snap_tap.snapshots import SnapshotArtifactRef, SnapshotBounds
from snap_tap.targets.models import (
    SNAPSHOT_TARGETS_SCHEMA_VERSION,
    SnapshotTarget,
    SnapshotTargets,
    SnapshotTargetsError,
    SnapshotTargetSummary,
)


__all__ = [
    "SnapshotTargetsError",
    "build_snapshot_targets",
    "snapshot_targets_to_dict",
]


def build_snapshot_targets(snapshot: SemanticSnapshot) -> SnapshotTargets:
    if snapshot.schema_version != SEMANTIC_SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotTargetsError(
            code="snapshot_targets_unsupported_version",
            detail="Snapshot targets require semantic_snapshot.v1 input.",
        )
    if not snapshot.snapshot_id or not snapshot.device_id or not snapshot.captured_at:
        raise SnapshotTargetsError(
            code="snapshot_targets_input_invalid",
            detail="Snapshot targets require semantic snapshot identity fields.",
        )

    targets = tuple(
        _snapshot_target(
            element=element,
            snapshot_id=snapshot.snapshot_id,
            semantic_index=semantic_index,
        )
        for semantic_index, element in enumerate(snapshot.elements)
    )
    return SnapshotTargets(
        schema_version=SNAPSHOT_TARGETS_SCHEMA_VERSION,
        snapshot_id=snapshot.snapshot_id,
        device_id=snapshot.device_id,
        captured_at=snapshot.captured_at,
        source_schema_version=snapshot.schema_version,
        refs=dict(snapshot.refs),
        targets=targets,
        summary=_summary(targets),
    )


def snapshot_targets_to_dict(snapshot_targets: SnapshotTargets) -> dict[str, object]:
    return {
        "schema_version": snapshot_targets.schema_version,
        "snapshot_id": snapshot_targets.snapshot_id,
        "device_id": snapshot_targets.device_id,
        "captured_at": snapshot_targets.captured_at,
        "source_schema_version": snapshot_targets.source_schema_version,
        "refs": {
            name: _snapshot_artifact_ref_to_dict(name, ref)
            for name, ref in snapshot_targets.refs.items()
        },
        "targets": [
            _snapshot_target_to_dict(target) for target in snapshot_targets.targets
        ],
        "summary": _summary_to_dict(snapshot_targets.summary),
    }


def _snapshot_target(
    *,
    element: SemanticElement,
    snapshot_id: str,
    semantic_index: int,
) -> SnapshotTarget:
    _validate_element(element)
    return SnapshotTarget(
        display_id=f"e{semantic_index + 1:03d}",
        snapshot_id=snapshot_id,
        semantic_index=semantic_index,
        source_index=element.source_index,
        role=element.role,
        bounds=element.bounds,
        enabled=element.enabled,
        clickable=element.clickable,
        scrollable=element.scrollable,
        actionable=element.enabled and element.clickable,
        label=element.label,
        label_source=element.label_source,
        class_name=element.class_name,
        resource_id=element.resource_id,
        package=element.package,
    )


def _validate_element(element: object) -> SemanticElement:
    if not isinstance(element, SemanticElement):
        raise SnapshotTargetsError(
            code="snapshot_targets_input_invalid",
            detail="Snapshot targets require semantic elements.",
        )
    _required_int(element.source_index, "element.source_index")
    if not isinstance(element.role, SemanticRole):
        raise SnapshotTargetsError(
            code="snapshot_targets_input_invalid",
            detail="Semantic element role must be a semantic role.",
        )
    if not isinstance(element.bounds, SnapshotBounds):
        raise SnapshotTargetsError(
            code="snapshot_targets_input_invalid",
            detail="Semantic element bounds are invalid.",
        )
    _required_bool(element.enabled, "element.enabled")
    _required_bool(element.clickable, "element.clickable")
    _required_bool(element.scrollable, "element.scrollable")
    _optional_text(element.label, "element.label")
    _required_text(element.label_source, "element.label_source")
    _optional_text(element.class_name, "element.class_name")
    _optional_text(element.resource_id, "element.resource_id")
    _optional_text(element.package, "element.package")
    if not isinstance(element.accessibility, Mapping):
        raise SnapshotTargetsError(
            code="snapshot_targets_input_invalid",
            detail="Semantic element accessibility must be a mapping.",
        )
    return element


def _summary(targets: tuple[SnapshotTarget, ...]) -> SnapshotTargetSummary:
    return SnapshotTargetSummary(
        target_count=len(targets),
        actionable_count=sum(1 for target in targets if target.actionable),
        disabled_count=sum(1 for target in targets if not target.enabled),
        non_clickable_count=sum(1 for target in targets if not target.clickable),
        scrollable_count=sum(1 for target in targets if target.scrollable),
        labeled_count=sum(1 for target in targets if target.label is not None),
        source_element_count=len(targets),
    )


def _snapshot_target_to_dict(target: SnapshotTarget) -> dict[str, object]:
    payload: dict[str, object] = {
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
        "label": target.label,
        "label_source": target.label_source,
    }
    if target.class_name is not None:
        payload["class_name"] = target.class_name
    if target.resource_id is not None:
        payload["resource_id"] = target.resource_id
    if target.package is not None:
        payload["package"] = target.package
    return payload


def _summary_to_dict(summary: SnapshotTargetSummary | None) -> dict[str, object] | None:
    if summary is None:
        return None
    return {
        "target_count": summary.target_count,
        "actionable_count": summary.actionable_count,
        "disabled_count": summary.disabled_count,
        "non_clickable_count": summary.non_clickable_count,
        "scrollable_count": summary.scrollable_count,
        "labeled_count": summary.labeled_count,
        "source_element_count": summary.source_element_count,
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


def _required_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SnapshotTargetsError(
            code="snapshot_targets_input_invalid",
            detail=f"{field_name} must be a non-negative integer.",
        )
    return value


def _required_bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise SnapshotTargetsError(
            code="snapshot_targets_input_invalid",
            detail=f"{field_name} must be a boolean.",
        )
    return value


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise SnapshotTargetsError(
            code="snapshot_targets_input_invalid",
            detail=f"{field_name} must be text.",
        )
    normalized = value.strip()
    if not normalized:
        raise SnapshotTargetsError(
            code="snapshot_targets_input_invalid",
            detail=f"{field_name} must not be empty.",
        )
    if normalized != value:
        raise SnapshotTargetsError(
            code="snapshot_targets_input_invalid",
            detail=f"{field_name} must already be normalized.",
        )
    return normalized


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field_name)
