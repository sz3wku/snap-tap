from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
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
    TargetSignature,
    TargetSignatureRequirements,
    build_snapshot_targets,
    build_target_signature,
    resolve_target_signature,
    target_resolution_to_dict,
)


def test_target_resolution_blocks_malformed_allowed_ref_before_ok() -> None:
    fresh = replace(
        _fresh_snapshot(),
        refs={"xml": cast(SnapshotArtifactRef, object())},
    )

    payload = _resolve_payload(_signature(), fresh)

    _assert_blocked(payload, "target_resolution_invalid_snapshot")
    assert payload["refs"] == {}


def test_target_resolution_blocks_malformed_refs_container_before_ok() -> None:
    fresh = replace(
        _fresh_snapshot(),
        refs=cast(Mapping[str, SnapshotArtifactRef], object()),
    )

    payload = _resolve_payload(_signature(), fresh)

    _assert_blocked(payload, "target_resolution_invalid_snapshot")
    assert payload["refs"] == {}


def test_target_resolution_blocks_malformed_fresh_target_bounds_before_ok() -> None:
    bad_element = replace(
        _save_element(1),
        bounds=cast(SnapshotBounds, object()),
    )

    payload = _resolve_payload(
        _signature(),
        _snapshot("snap_fresh", (bad_element,)),
    )

    _assert_blocked(payload, "target_resolution_invalid_snapshot")


def test_target_resolution_blocks_unsafe_signature_requirements() -> None:
    payload = _resolve_payload(
        replace(
            _signature(),
            requirements=TargetSignatureRequirements(
                requires_fresh_snapshot=False,
                requires_resolution=False,
                not_executable_directly=False,
            ),
        ),
        _fresh_snapshot(),
    )

    _assert_blocked(payload, "target_resolution_invalid_signature")


def test_target_resolution_blocks_malformed_signature_identity_container() -> None:
    payload = _resolve_payload(
        replace(
            _signature(),
            identity=cast(Mapping[str, str], object()),
        ),
        _fresh_snapshot(),
    )

    _assert_blocked(payload, "target_resolution_invalid_signature")


def test_target_resolution_ignores_source_coordinates_and_local_ids() -> None:
    signature = replace(
        _signature(),
        display_id="e999",
        semantic_index=999,
        source_index=999,
        source_bounds=SnapshotBounds(900, 901, 902, 903, 2, 2, 901.0, 902.0),
    )

    payload = _resolve_payload(signature, _fresh_snapshot())

    assert payload["ok"] is True
    target = cast(dict[str, object], payload["resolved_target"])
    assert target["display_id"] == "e001"
    assert target["semantic_index"] == 0
    assert target["source_index"] == 1


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


def _fresh_snapshot() -> SemanticSnapshot:
    return _snapshot("snap_fresh", (_save_element(1),))


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


def _save_element(source_index: int) -> SemanticElement:
    return SemanticElement(
        source_index=source_index,
        role=SemanticRole.BUTTON,
        bounds=SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
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
