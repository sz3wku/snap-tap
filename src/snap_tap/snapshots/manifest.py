from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from snap_tap.snapshots.models import (
    RawSnapshotCapture,
    SnapshotArtifactRef,
    SnapshotBounds,
    SnapshotElement,
    SnapshotNormalization,
)

SNAPSHOT_MANIFEST_SCHEMA_VERSION = "snapshot_manifest.v1"


class SnapshotManifestError(Exception):
    pass


def build_snapshot_manifest(
    result: RawSnapshotCapture,
    *,
    capture_dir: Path,
) -> dict[str, object]:
    if result.identity is None:
        raise SnapshotManifestError("Snapshot manifest requires snapshot identity.")
    if result.device_id is None:
        raise SnapshotManifestError("Snapshot manifest requires device id.")
    if result.normalization is None:
        raise SnapshotManifestError("Snapshot manifest requires normalization.")
    xml_ref = _required_ref(result.refs, "xml")
    screenshot_ref = _required_ref(result.refs, "screenshot")
    return {
        "schema_version": SNAPSHOT_MANIFEST_SCHEMA_VERSION,
        "ok": result.ok,
        "status": result.status,
        "snapshot": {
            "snapshot_id": result.identity.snapshot_id,
            "snapshot_hash": result.identity.snapshot_hash,
            "hash_version": result.identity.hash_version,
        },
        "device": {
            "device_id": result.device_id,
            "backend": result.backend,
        },
        "operation": {
            "name": result.operation,
            "checked_at": result.checked_at,
            "elapsed_ms": result.elapsed_ms,
        },
        "artifacts": {
            "xml": _artifact_ref_to_manifest_dict(xml_ref, capture_dir=capture_dir),
            "screenshot": _artifact_ref_to_manifest_dict(
                screenshot_ref,
                capture_dir=capture_dir,
            ),
        },
        "normalization": _normalization_to_dict(result.normalization),
        "elements": [_element_to_dict(element) for element in result.elements],
        "metadata": _metadata_to_dict(result.metadata),
        "recovery": _recovery_to_dict(result.metadata),
    }


def encode_snapshot_manifest(payload: Mapping[str, object]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, indent=2, separators=(",", ": "))
        + "\n"
    ).encode("utf-8")


def _required_ref(
    refs: Mapping[str, SnapshotArtifactRef],
    name: str,
) -> SnapshotArtifactRef:
    try:
        return refs[name]
    except KeyError as exc:
        raise SnapshotManifestError(f"Snapshot manifest requires {name} ref.") from exc


def _artifact_ref_to_manifest_dict(
    ref: SnapshotArtifactRef,
    *,
    capture_dir: Path,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "path": _relative_artifact_path(ref.path, capture_dir),
        "sha256": ref.sha256,
        "byte_length": ref.byte_length,
    }
    metadata = dict(ref.metadata)
    for key in ("node_count", "width", "height"):
        value = metadata.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            payload[key] = value
    image_format = metadata.get("format")
    if isinstance(image_format, str):
        payload["format"] = image_format
    return payload


def _relative_artifact_path(path: str, capture_dir: Path) -> str:
    try:
        relative = Path(path).resolve(strict=False).relative_to(
            capture_dir.resolve(strict=False),
        )
    except ValueError as exc:
        raise SnapshotManifestError("Manifest artifact path escaped capture dir.") from exc
    return relative.as_posix()


def _normalization_to_dict(
    normalization: SnapshotNormalization,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": normalization.schema_version,
        "status": normalization.status,
        "source_node_count": normalization.source_node_count,
        "element_count": normalization.element_count,
        "visible_count": normalization.visible_count,
        "enabled_count": normalization.enabled_count,
        "clickable_count": normalization.clickable_count,
        "discarded_count": normalization.discarded_count,
        "invalid_bounds_count": normalization.invalid_bounds_count,
    }
    if normalization.viewport_width is not None:
        payload["viewport_width"] = normalization.viewport_width
    if normalization.viewport_height is not None:
        payload["viewport_height"] = normalization.viewport_height
    return payload


def _element_to_dict(element: SnapshotElement) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_index": element.source_index,
        "depth": element.depth,
        "bounds": _bounds_to_dict(element.bounds),
        "visible": element.visible,
        "enabled": element.enabled,
        "clickable": element.clickable,
    }
    if element.class_name is not None:
        payload["class_name"] = element.class_name
    if element.resource_id is not None:
        payload["resource_id"] = element.resource_id
    if element.package is not None:
        payload["package"] = element.package
    return payload


def _bounds_to_dict(bounds: SnapshotBounds) -> dict[str, object]:
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


def _metadata_to_dict(metadata: Mapping[str, object]) -> dict[str, object]:
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


def _recovery_to_dict(
    metadata: Mapping[str, object],
) -> dict[str, object] | None:
    public: dict[str, object] = {}
    xml_recovery = _nested_recovery_to_dict(metadata.get("xml_recovery"))
    if xml_recovery is not None:
        public["xml"] = xml_recovery
    screenshot_recovery = _nested_recovery_to_dict(
        metadata.get("screenshot_recovery"),
    )
    if screenshot_recovery is not None:
        public["screenshot"] = screenshot_recovery
    return public or None


def _nested_recovery_to_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    if value.get("recovery_attempted") is not True:
        return None
    public: dict[str, object] = {"recovery_attempted": True}
    attempt = value.get("attempt")
    if isinstance(attempt, int) and not isinstance(attempt, bool):
        public["attempt"] = attempt
    recovery_ok = value.get("recovery_ok")
    if isinstance(recovery_ok, bool):
        public["recovery_ok"] = recovery_ok
    for key in (
        "recovery_operation",
        "recovered_after_failure",
        "recovery_error_code",
    ):
        item = value.get(key)
        if isinstance(item, str):
            public[key] = item
    recovery_elapsed_ms = value.get("recovery_elapsed_ms")
    if isinstance(recovery_elapsed_ms, (int, float)) and not isinstance(
        recovery_elapsed_ms,
        bool,
    ):
        public["recovery_elapsed_ms"] = recovery_elapsed_ms
    return public
