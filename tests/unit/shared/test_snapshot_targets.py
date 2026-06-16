from __future__ import annotations

import pytest

from typing import cast

from snap_tap.semantics import (
    SEMANTIC_SCREEN_METADATA_SCHEMA_VERSION,
    SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
    SemanticElement,
    SemanticRole,
    SemanticScreenCounts,
    SemanticScreenMetadata,
    SemanticSnapshot,
    SemanticViewport,
    ViewportOrientation,
)
from snap_tap.snapshots import SnapshotArtifactRef, SnapshotBounds
from snap_tap.targets import (
    SnapshotTargetsError,
    build_snapshot_targets,
    snapshot_targets_to_dict,
)


def test_snapshot_targets_use_semantic_order_and_bind_snapshot_identity() -> None:
    payload = _target_payload()
    targets = cast(list[dict[str, object]], payload["targets"])

    assert [target["display_id"] for target in targets] == ["e001", "e002", "e003"]
    assert [target["snapshot_id"] for target in targets] == ["snap_targets"] * 3
    assert [target["semantic_index"] for target in targets] == [0, 1, 2]
    assert [target["source_index"] for target in targets] == [9, 3, 7]


def test_snapshot_targets_copy_observation_fields_and_summary_counts() -> None:
    payload = _target_payload()
    targets = cast(list[dict[str, object]], payload["targets"])

    assert targets[0] == {
        "display_id": "e001",
        "snapshot_id": "snap_targets",
        "semantic_index": 0,
        "source_index": 9,
        "role": "button",
        "bounds": _bounds_dict(),
        "enabled": True,
        "clickable": True,
        "scrollable": False,
        "actionable": True,
        "label": "Save",
        "label_source": "content_desc",
        "class_name": "android.widget.Button",
        "resource_id": "com.example:id/save",
        "package": "com.example",
    }
    assert targets[1]["actionable"] is False
    assert targets[2]["actionable"] is False
    assert payload["summary"] == {
        "target_count": 3,
        "actionable_count": 1,
        "disabled_count": 1,
        "non_clickable_count": 2,
        "scrollable_count": 0,
        "labeled_count": 2,
        "source_element_count": 3,
    }


def test_snapshot_targets_empty_semantics_have_no_fallback_handles() -> None:
    payload = snapshot_targets_to_dict(build_snapshot_targets(_snapshot(())))

    assert payload["targets"] == []
    assert payload["summary"] == {
        "target_count": 0,
        "actionable_count": 0,
        "disabled_count": 0,
        "non_clickable_count": 0,
        "scrollable_count": 0,
        "labeled_count": 0,
        "source_element_count": 0,
    }


def test_snapshot_targets_are_deterministic_for_same_semantic_snapshot() -> None:
    snapshot = _snapshot(_elements())

    assert snapshot_targets_to_dict(build_snapshot_targets(snapshot)) == (
        snapshot_targets_to_dict(build_snapshot_targets(snapshot))
    )


def test_snapshot_targets_fail_closed_for_unsupported_semantic_version() -> None:
    snapshot = _snapshot(_elements(), schema_version="future.v2")

    with pytest.raises(SnapshotTargetsError) as exc_info:
        build_snapshot_targets(snapshot)

    assert exc_info.value.code == "snapshot_targets_unsupported_version"


def _target_payload() -> dict[str, object]:
    return snapshot_targets_to_dict(build_snapshot_targets(_snapshot(_elements())))


def _snapshot(
    elements: tuple[SemanticElement, ...],
    *,
    schema_version: str = SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
) -> SemanticSnapshot:
    return SemanticSnapshot(
        schema_version=schema_version,
        snapshot_id="snap_targets",
        device_id="RFCN4010FCK",
        captured_at="2026-06-14T10:00:00+00:00",
        refs=_refs(len(elements)),
        elements=elements,
        screen_metadata=SemanticScreenMetadata(
            schema_version=SEMANTIC_SCREEN_METADATA_SCHEMA_VERSION,
            viewport=SemanticViewport(
                orientation=ViewportOrientation.PORTRAIT,
                width=1080,
                height=2400,
            ),
            counts=SemanticScreenCounts(
                source_element_count=len(elements),
                visible_element_count=len(elements),
                semantic_element_count=len(elements),
                enabled_count=sum(1 for element in elements if element.enabled),
                clickable_count=sum(1 for element in elements if element.clickable),
                actionable_count=sum(
                    1 for element in elements if element.enabled and element.clickable
                ),
                labeled_count=sum(1 for element in elements if element.label),
                unknown_count=sum(
                    1 for element in elements if element.role == SemanticRole.UNKNOWN
                ),
            ),
        ),
    )


def _elements() -> tuple[SemanticElement, ...]:
    return (
        _element(9, SemanticRole.BUTTON, True, True, "Save", "content_desc"),
        _element(3, SemanticRole.INPUT, True, False, "Name", "text"),
        _element(7, SemanticRole.UNKNOWN, False, False, None, "none"),
    )


def _element(
    source_index: int,
    role: SemanticRole,
    enabled: bool,
    clickable: bool,
    label: str | None,
    label_source: str,
) -> SemanticElement:
    return SemanticElement(
        source_index=source_index,
        role=role,
        bounds=_bounds(),
        enabled=enabled,
        clickable=clickable,
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
