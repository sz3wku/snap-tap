from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from math import isfinite

from snap_tap.semantics import SemanticRole
from snap_tap.snapshots import LatestSnapshotRefError, SnapshotBounds
from snap_tap.snapshots.latest_types import (
    normalize_latest_snapshot_device_id,
    normalize_latest_snapshot_session_id,
)
from snap_tap.targets.latest_snap_source_models import (
    LATEST_SNAP_SOURCE_SCHEMA_VERSION,
    LatestSnapSource,
    LatestSnapSourceSnapshot,
    LatestSnapSourceTarget,
    invalid_latest_snap_source,
    unsupported_latest_snap_source,
)
from snap_tap.targets.models import MobileSnapKind


def latest_snap_source_to_dict(source: LatestSnapSource) -> dict[str, object]:
    if source.schema_version != LATEST_SNAP_SOURCE_SCHEMA_VERSION:
        raise unsupported_latest_snap_source()
    return {
        "schema_version": source.schema_version,
        "device_id": normalize_latest_snapshot_device_id(source.device_id),
        "session_id": normalize_latest_snapshot_session_id(source.session_id),
        "updated_at": required_text(source.updated_at, "updated_at"),
        "snapshot": {
            "snapshot_id": required_text(
                source.snapshot.snapshot_id,
                "snapshot.snapshot_id",
            ),
            "captured_at": required_text(
                source.snapshot.captured_at,
                "snapshot.captured_at",
            ),
            "source_schema_version": required_text(
                source.snapshot.source_schema_version,
                "snapshot.source_schema_version",
            ),
        },
        "targets": [_target_to_dict(target) for target in source.targets],
    }


def latest_snap_source_from_dict(payload: object) -> LatestSnapSource:
    if not isinstance(payload, Mapping):
        raise invalid_latest_snap_source("Latest snap source must be a JSON object.")
    if set(payload) != {
        "schema_version",
        "device_id",
        "session_id",
        "updated_at",
        "snapshot",
        "targets",
    }:
        raise invalid_latest_snap_source(
            "Latest snap source contains invalid fields."
        )
    version = payload.get("schema_version")
    if version != LATEST_SNAP_SOURCE_SCHEMA_VERSION:
        raise unsupported_latest_snap_source()
    snapshot = mapping(payload.get("snapshot"), "snapshot")
    return LatestSnapSource(
        schema_version=LATEST_SNAP_SOURCE_SCHEMA_VERSION,
        device_id=normalize_latest_snapshot_device_id(payload.get("device_id")),
        session_id=normalize_latest_snapshot_session_id(payload.get("session_id")),
        updated_at=required_text(payload.get("updated_at"), "updated_at"),
        snapshot=LatestSnapSourceSnapshot(
            snapshot_id=required_text(
                snapshot.get("snapshot_id"),
                "snapshot.snapshot_id",
            ),
            captured_at=required_text(
                snapshot.get("captured_at"),
                "snapshot.captured_at",
            ),
            source_schema_version=required_text(
                snapshot.get("source_schema_version"),
                "snapshot.source_schema_version",
            ),
        ),
        targets=tuple(_target_from_payload(item) for item in _targets(payload)),
    )


def encode_latest_snap_source(source: LatestSnapSource) -> bytes:
    return (
        json.dumps(
            latest_snap_source_to_dict(source),
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")


def required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise invalid_latest_snap_source(f"{field_name} must be text.")
    normalized = value.strip()
    if not normalized:
        raise invalid_latest_snap_source(f"{field_name} must not be empty.")
    if normalized != value:
        raise invalid_latest_snap_source(
            f"{field_name} must already be normalized."
        )
    return normalized


def optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return required_text(value, field_name)


def non_negative_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise invalid_latest_snap_source(
            f"{field_name} must be a non-negative integer."
        )
    return value


def non_negative_number(value: object, field_name: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not isfinite(value)
        or value < 0
    ):
        raise invalid_latest_snap_source(
            f"{field_name} must be a non-negative finite number."
        )
    return float(value)


def boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise invalid_latest_snap_source(f"{field_name} must be a boolean.")
    return value


def mapping(value: object, field_name: str) -> Mapping[object, object]:
    if not isinstance(value, Mapping):
        raise invalid_latest_snap_source(f"{field_name} must be an object.")
    return value


def role_from_value(value: object) -> SemanticRole:
    text = required_text(value, "role")
    try:
        return SemanticRole(text)
    except ValueError as exc:
        raise invalid_latest_snap_source(
            "Latest snap source target role is unsupported."
        ) from exc


def kind_from_value(value: object) -> MobileSnapKind:
    text = required_text(value, "kind")
    try:
        return MobileSnapKind(text)
    except ValueError as exc:
        raise invalid_latest_snap_source(
            "Latest snap source target kind is unsupported."
        ) from exc


def latest_snapshot_error_to_snap_source_error(exc: LatestSnapshotRefError) -> str:
    return exc.detail


def target_to_dict(target: LatestSnapSourceTarget) -> dict[str, object]:
    return _target_to_dict(target)


def bounds_from_payload(value: object) -> SnapshotBounds:
    payload = mapping(value, "bounds")
    return SnapshotBounds(
        left=non_negative_int(payload.get("left"), "bounds.left"),
        top=non_negative_int(payload.get("top"), "bounds.top"),
        right=non_negative_int(payload.get("right"), "bounds.right"),
        bottom=non_negative_int(payload.get("bottom"), "bounds.bottom"),
        width=non_negative_int(payload.get("width"), "bounds.width"),
        height=non_negative_int(payload.get("height"), "bounds.height"),
        center_x=non_negative_number(payload.get("center_x"), "bounds.center_x"),
        center_y=non_negative_number(payload.get("center_y"), "bounds.center_y"),
    )


def bounds_to_dict(bounds: SnapshotBounds) -> dict[str, object]:
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


def _target_to_dict(target: LatestSnapSourceTarget) -> dict[str, object]:
    payload: dict[str, object] = {
        "display_id": required_text(target.display_id, "target.display_id"),
        "snapshot_id": required_text(target.snapshot_id, "target.snapshot_id"),
        "semantic_index": non_negative_int(
            target.semantic_index,
            "target.semantic_index",
        ),
        "source_index": non_negative_int(
            target.source_index,
            "target.source_index",
        ),
        "role": target.role.value,
        "kind": target.kind.value,
        "bounds": bounds_to_dict(target.bounds),
        "enabled": boolean(target.enabled, "target.enabled"),
        "clickable": boolean(target.clickable, "target.clickable"),
        "scrollable": boolean(target.scrollable, "target.scrollable"),
        "actionable": boolean(target.actionable, "target.actionable"),
        "label": target.label,
        "label_source": required_text(target.label_source, "target.label_source"),
    }
    for key in ("class_name", "resource_id", "package"):
        value = getattr(target, key)
        if value is not None:
            payload[key] = required_text(value, f"target.{key}")
    return payload


def _target_from_payload(payload: object) -> LatestSnapSourceTarget:
    target = mapping(payload, "target")
    allowed = {
        "display_id",
        "snapshot_id",
        "semantic_index",
        "source_index",
        "role",
        "kind",
        "bounds",
        "enabled",
        "clickable",
        "scrollable",
        "actionable",
        "label",
        "label_source",
        "class_name",
        "resource_id",
        "package",
    }
    if set(target) - allowed:
        raise invalid_latest_snap_source(
            "Latest snap source target contains invalid fields."
        )
    return LatestSnapSourceTarget(
        display_id=required_text(target.get("display_id"), "target.display_id"),
        snapshot_id=required_text(target.get("snapshot_id"), "target.snapshot_id"),
        semantic_index=non_negative_int(
            target.get("semantic_index"),
            "target.semantic_index",
        ),
        source_index=non_negative_int(
            target.get("source_index"),
            "target.source_index",
        ),
        role=role_from_value(target.get("role")),
        kind=kind_from_value(target.get("kind")),
        bounds=bounds_from_payload(target.get("bounds")),
        enabled=boolean(target.get("enabled"), "target.enabled"),
        clickable=boolean(target.get("clickable"), "target.clickable"),
        scrollable=boolean(target.get("scrollable"), "target.scrollable"),
        actionable=boolean(target.get("actionable"), "target.actionable"),
        label=optional_text(target.get("label"), "target.label"),
        label_source=required_text(target.get("label_source"), "target.label_source"),
        class_name=optional_text(target.get("class_name"), "target.class_name"),
        resource_id=optional_text(target.get("resource_id"), "target.resource_id"),
        package=optional_text(target.get("package"), "target.package"),
    )


def _targets(payload: Mapping[object, object]) -> Sequence[object]:
    targets = payload.get("targets")
    if not isinstance(targets, Sequence) or isinstance(targets, (str, bytes)):
        raise invalid_latest_snap_source("Latest snap source targets must be a list.")
    return targets
