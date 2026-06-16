from __future__ import annotations

from collections.abc import Mapping

from snap_tap.cli.output import error_to_dict, recovery_to_dict
from snap_tap.semantics import build_semantic_snapshot, semantic_snapshot_to_dict
from snap_tap.snapshots import (
    RawSnapshotCapture,
    SnapshotArtifactRef,
    SnapshotBounds,
    SnapshotElement,
    SnapshotNormalization,
)


def raw_snapshot_capture_to_dict(result: RawSnapshotCapture) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": result.ok,
        "status": result.status,
        "device_id": result.device_id,
        "backend": result.backend,
        "operation": result.operation,
        "snapshot_id": (
            result.identity.snapshot_id if result.identity is not None else None
        ),
        "snapshot_hash": (
            result.identity.snapshot_hash if result.identity is not None else None
        ),
        "hash_version": (
            result.identity.hash_version if result.identity is not None else None
        ),
        "checked_at": result.checked_at,
        "elapsed_ms": result.elapsed_ms,
        "refs": {
            name: snapshot_artifact_ref_to_dict(name, ref)
            for name, ref in result.refs.items()
        },
        "elements": [snapshot_element_to_dict(element) for element in result.elements],
        "semantics": _semantics_to_dict(result),
        "normalization": snapshot_normalization_to_dict(result.normalization),
        "metadata": raw_snapshot_metadata_to_dict(result.metadata),
        "recovery": raw_snapshot_recovery_to_dict(result.metadata),
        "error": error_to_dict(result.error),
    }
    return payload


def _semantics_to_dict(result: RawSnapshotCapture) -> dict[str, object] | None:
    if not result.ok:
        return None
    return semantic_snapshot_to_dict(build_semantic_snapshot(result))


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
        manifest_metadata: dict[str, object] = {}
        if isinstance(schema_version, str):
            manifest_metadata["schema_version"] = schema_version
        if manifest_metadata:
            payload["metadata"] = manifest_metadata
    return payload


def snapshot_element_to_dict(element: SnapshotElement) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_index": element.source_index,
        "depth": element.depth,
        "bounds": snapshot_bounds_to_dict(element.bounds),
        "visible": element.visible,
        "enabled": element.enabled,
        "clickable": element.clickable,
        "scrollable": element.scrollable,
    }
    if element.class_name is not None:
        payload["class_name"] = element.class_name
    if element.resource_id is not None:
        payload["resource_id"] = element.resource_id
    if element.package is not None:
        payload["package"] = element.package
    return payload


def snapshot_bounds_to_dict(bounds: SnapshotBounds) -> dict[str, object]:
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


def snapshot_normalization_to_dict(
    normalization: SnapshotNormalization | None,
) -> dict[str, object] | None:
    if normalization is None:
        return None
    payload: dict[str, object] = {
        "schema_version": normalization.schema_version,
        "status": normalization.status,
        "source_node_count": normalization.source_node_count,
        "element_count": normalization.element_count,
        "visible_count": normalization.visible_count,
        "enabled_count": normalization.enabled_count,
        "clickable_count": normalization.clickable_count,
        "scrollable_count": normalization.scrollable_count,
        "discarded_count": normalization.discarded_count,
        "invalid_bounds_count": normalization.invalid_bounds_count,
    }
    if normalization.viewport_width is not None:
        payload["viewport_width"] = normalization.viewport_width
    if normalization.viewport_height is not None:
        payload["viewport_height"] = normalization.viewport_height
    return payload


def raw_snapshot_metadata_to_dict(
    metadata: Mapping[str, object],
) -> dict[str, object]:
    public: dict[str, object] = {}
    for key in ("stage", "source_error_code"):
        value = metadata.get(key)
        if isinstance(value, str):
            public[key] = value
    for key in (
        "timeout_s",
        "source_elapsed_ms",
        "xml_elapsed_ms",
        "screenshot_elapsed_ms",
    ):
        value = metadata.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            public[key] = value
    return public


def raw_snapshot_recovery_to_dict(
    metadata: Mapping[str, object],
) -> dict[str, object] | None:
    public: dict[str, object] = {}
    xml_recovery = _nested_recovery_to_dict(metadata.get("xml_recovery"))
    if xml_recovery is not None:
        public["xml"] = xml_recovery
    screenshot_recovery = _nested_recovery_to_dict(
        metadata.get("screenshot_recovery")
    )
    if screenshot_recovery is not None:
        public["screenshot"] = screenshot_recovery
    return public or None


def _nested_recovery_to_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return recovery_to_dict(value)
