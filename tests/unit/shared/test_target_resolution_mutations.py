from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import cast

import pytest

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
    TargetSignature,
    build_snapshot_targets,
    build_target_signature,
    resolve_target_signature,
    target_resolution_to_dict,
)


def test_target_resolution_ignores_source_handle_and_coordinate_mutations() -> None:
    signature = replace(
        _signature(),
        display_id="e999",
        semantic_index=999,
        source_index=999,
        source_bounds=SnapshotBounds(900, 901, 902, 903, 2, 2, 901.0, 902.0),
    )

    payload = _resolve_payload(
        signature,
        _snapshot(
            "snap_fresh",
            (
                _save_element(
                    555,
                    bounds=SnapshotBounds(40, 50, 340, 350, 300, 300, 190.0, 200.0),
                ),
            ),
        ),
    )

    assert payload["ok"] is True
    target = cast(dict[str, object], payload["resolved_target"])
    assert target["display_id"] == "e001"
    assert target["semantic_index"] == 0
    assert target["source_index"] == 555
    assert target["bounds"] == {
        "left": 40,
        "top": 50,
        "right": 340,
        "bottom": 350,
        "width": 300,
        "height": 300,
        "center_x": 190.0,
        "center_y": 200.0,
    }


@pytest.mark.parametrize(
    ("name", "mutate"),
    (
        ("resource_id", lambda element: replace(element, resource_id="changed:id")),
        ("label", lambda element: replace(element, label="Changed")),
        ("label_source", lambda element: replace(element, label_source="text")),
        ("class_name", lambda element: replace(element, class_name="ChangedClass")),
        ("package", lambda element: replace(element, package="changed.package")),
        ("role", lambda element: replace(element, role=SemanticRole.TAB)),
    ),
)
def test_target_resolution_blocks_exact_identity_mutations(
    name: str,
    mutate: Callable[[SemanticElement], SemanticElement],
) -> None:
    del name
    payload = _resolve_payload(
        _signature(),
        _snapshot("snap_fresh", (mutate(_save_element(1)),)),
    )

    _assert_blocked(payload, "target_resolution_no_match")


def test_target_resolution_does_not_fallback_to_coordinates_when_identity_changes() -> None:
    source = _save_element(9)
    signature = build_target_signature(
        build_snapshot_targets(_snapshot("snap_source", (source,))),
        "e001",
    )
    same_coordinates_different_identity = replace(
        source,
        source_index=1,
        label="Changed",
    )

    payload = _resolve_payload(
        signature,
        _snapshot("snap_fresh", (same_coordinates_different_identity,)),
    )

    _assert_blocked(payload, "target_resolution_no_match")


def test_target_resolution_does_not_use_coordinates_to_disambiguate() -> None:
    source = _save_element(9)
    signature = build_target_signature(
        build_snapshot_targets(_snapshot("snap_source", (source,))),
        "e001",
    )
    same_coordinates = replace(source, source_index=1)
    shifted_coordinates = replace(
        source,
        source_index=2,
        bounds=SnapshotBounds(500, 600, 700, 800, 200, 200, 600.0, 700.0),
    )

    payload = _resolve_payload(
        signature,
        _snapshot("snap_fresh", (same_coordinates, shifted_coordinates)),
    )

    _assert_blocked(payload, "target_resolution_ambiguous")
    assert cast(dict[str, object], payload["match"])["candidate_count"] == 2


def _resolve_payload(
    signature: TargetSignature,
    snapshot: SemanticSnapshot,
) -> dict[str, object]:
    return target_resolution_to_dict(resolve_target_signature(signature, snapshot))


def _assert_blocked(payload: dict[str, object], code: str) -> None:
    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert "resolved_target" not in payload
    blocking_reason = cast(dict[str, object], payload["blocking_reason"])
    assert blocking_reason["code"] == code
    assert blocking_reason["touched_phone"] is False


def _signature() -> TargetSignature:
    return build_target_signature(
        build_snapshot_targets(_snapshot("snap_source", (_save_element(9),))),
        "e001",
    )


def _snapshot(
    snapshot_id: str,
    elements: tuple[SemanticElement, ...],
) -> SemanticSnapshot:
    return SemanticSnapshot(
        schema_version=SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
        snapshot_id=snapshot_id,
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


def _save_element(
    source_index: int,
    *,
    bounds: SnapshotBounds | None = None,
) -> SemanticElement:
    return SemanticElement(
        source_index=source_index,
        role=SemanticRole.BUTTON,
        bounds=bounds or SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
        enabled=True,
        clickable=True,
        label="Save",
        label_source="content_desc",
        class_name="android.widget.Button",
        resource_id="com.example:id/save",
        package="com.example",
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
