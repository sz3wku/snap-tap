from __future__ import annotations

from dataclasses import replace

import pytest

from snap_tap.semantics import SemanticRole
from snap_tap.snapshots import SnapshotArtifactRef, SnapshotBounds
from snap_tap.targets import (
    SnapshotTarget,
    SnapshotTargets,
    TargetSignatureError,
    build_target_signature,
    target_signature_to_dict,
)


def test_target_signature_binds_source_target_identity() -> None:
    payload = _signature_payload("e001")

    assert payload["schema_version"] == "target_signature.v1"
    assert str(payload["signature_id"]).startswith("target_signature:")
    assert payload["source_snapshot_id"] == "snap_targets"
    assert payload["device_id"] == "RFCN4010FCK"
    assert payload["captured_at"] == "2026-06-14T10:00:00+00:00"
    assert payload["display_id"] == "e001"
    assert payload["semantic_index"] == 0
    assert payload["source_index"] == 9
    assert payload["role"] == "button"
    assert payload["identity"] == {
        "label": "Save",
        "label_source": "content_desc",
        "resource_id": "com.example:id/save",
        "class_name": "android.widget.Button",
        "package": "com.example",
        "role": "button",
    }
    assert payload["source_bounds"] == _bounds_dict()
    assert payload["requirements"] == {
        "requires_fresh_snapshot": True,
        "requires_resolution": True,
        "not_executable_directly": True,
    }
    assert payload["identity_strength"] == "strong"


def test_target_signature_id_is_deterministic_for_same_source_target() -> None:
    first = _signature_payload("e001")
    second = _signature_payload("e001")

    assert first["signature_id"] == second["signature_id"]


def test_target_signature_can_record_weaker_non_coordinate_identity() -> None:
    payload = _signature_payload("e002")

    assert payload["identity"] == {"role": "input"}
    assert payload["identity_strength"] == "weak"


def test_target_signature_fails_closed_for_missing_display_id() -> None:
    with pytest.raises(TargetSignatureError) as exc_info:
        build_target_signature(_snapshot_targets(), "e999")

    assert exc_info.value.code == "target_signature_missing"


def test_target_signature_fails_closed_for_duplicate_display_id() -> None:
    source = _snapshot_targets()
    duplicate_targets = (
        source.targets[0],
        replace(source.targets[1], display_id=source.targets[0].display_id),
    )
    source = replace(source, targets=duplicate_targets)

    with pytest.raises(TargetSignatureError) as exc_info:
        build_target_signature(source, "e001")

    assert exc_info.value.code == "target_signature_duplicate_display_id"


def test_target_signature_fails_closed_for_unsupported_source_schema() -> None:
    source = replace(_snapshot_targets(), schema_version="future.targets.v2")

    with pytest.raises(TargetSignatureError) as exc_info:
        build_target_signature(source, "e001")

    assert exc_info.value.code == "target_signature_unsupported_version"


def test_target_signature_fails_closed_for_bounds_only_identity() -> None:
    source = _snapshot_targets(
        (
            _target(9, SemanticRole.UNKNOWN, True, True, None, "none"),
        )
    )

    with pytest.raises(TargetSignatureError) as exc_info:
        build_target_signature(source, "e001")

    assert exc_info.value.code == "target_signature_insufficient_identity"


def test_target_signature_fails_closed_for_invalid_identity_fields() -> None:
    source = _snapshot_targets()
    source = replace(source, targets=(replace(source.targets[0], label="   "),))

    with pytest.raises(TargetSignatureError) as exc_info:
        build_target_signature(source, "e001")

    assert exc_info.value.code == "target_signature_invalid"


def _signature_payload(display_id: str) -> dict[str, object]:
    return target_signature_to_dict(
        build_target_signature(_snapshot_targets(), display_id)
    )


def _snapshot_targets(
    targets: tuple[SnapshotTarget, ...] | None = None,
) -> SnapshotTargets:
    source_targets = targets or _targets()
    return SnapshotTargets(
        schema_version="snapshot_targets.v1",
        snapshot_id="snap_targets",
        device_id="RFCN4010FCK",
        captured_at="2026-06-14T10:00:00+00:00",
        source_schema_version="semantic_snapshot.v1",
        refs=_refs(len(source_targets)),
        targets=source_targets,
    )


def _targets() -> tuple[SnapshotTarget, ...]:
    return (
        _target(9, SemanticRole.BUTTON, True, True, "Save", "content_desc"),
        _target(3, SemanticRole.INPUT, True, False, None, "none"),
    )


def _target(
    source_index: int,
    role: SemanticRole,
    enabled: bool,
    clickable: bool,
    label: str | None,
    label_source: str,
) -> SnapshotTarget:
    semantic_index = 0 if source_index == 9 else 1
    return SnapshotTarget(
        display_id=f"e{semantic_index + 1:03d}",
        snapshot_id="snap_targets",
        semantic_index=semantic_index,
        source_index=source_index,
        role=role,
        bounds=_bounds(),
        enabled=enabled,
        clickable=clickable,
        actionable=enabled and clickable,
        label=label,
        label_source=label_source,
        class_name="android.widget.Button" if label == "Save" else None,
        resource_id="com.example:id/save" if label == "Save" else None,
        package="com.example" if label == "Save" else None,
    )


def _refs(node_count: int) -> dict[str, SnapshotArtifactRef]:
    return {
        "xml": SnapshotArtifactRef(
            path="screen.xml",
            sha256="xml-sha",
            byte_length=123,
            metadata={"node_count": node_count},
        )
    }


def _bounds() -> SnapshotBounds:
    return SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0)


def _bounds_dict() -> dict[str, object]:
    return {
        "left": 10,
        "top": 20,
        "right": 110,
        "bottom": 220,
        "width": 100,
        "height": 200,
        "center_x": 60.0,
        "center_y": 120.0,
    }
