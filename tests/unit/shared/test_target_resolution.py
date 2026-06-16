from __future__ import annotations

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
    build_snapshot_targets,
    build_target_signature,
    resolve_target_signature,
    target_resolution_to_dict,
)


def test_target_resolution_resolves_unique_actionable_fresh_match() -> None:
    signature = _signature()
    payload = _resolve_payload(
        signature,
        _snapshot(
            "snap_fresh",
            (
                _element(
                    42,
                    SemanticRole.UNKNOWN,
                    True,
                    True,
                    "Other",
                    "text",
                ),
                _save_element(
                    source_index=77,
                    bounds=SnapshotBounds(200, 300, 500, 700, 300, 400, 350.0, 500.0),
                ),
            ),
        ),
    )

    assert payload["schema_version"] == "target_resolution.v1"
    assert payload["ok"] is True
    assert payload["status"] == "resolved"
    assert payload["signature_id"] == signature.signature_id
    assert payload["source_snapshot_id"] == "snap_source"
    assert payload["resolved_snapshot_id"] == "snap_fresh"
    assert payload["device_id"] == "RFCN4010FCK"
    assert "blocking_reason" not in payload

    target = cast(dict[str, object], payload["resolved_target"])
    assert target["display_id"] == "e002"
    assert target["snapshot_id"] == "snap_fresh"
    assert target["semantic_index"] == 1
    assert target["source_index"] == 77
    assert target["bounds"] == {
        "left": 200,
        "top": 300,
        "right": 500,
        "bottom": 700,
        "width": 300,
        "height": 400,
        "center_x": 350.0,
        "center_y": 500.0,
    }
    assert target["enabled"] is True
    assert target["clickable"] is True
    assert target["actionable"] is True
    assert payload["match"] == {
        "identity_strength": "strong",
        "matched_fields": [
            "resource_id",
            "label",
            "label_source",
            "class_name",
            "package",
            "role",
        ],
        "candidate_count": 1,
    }


def test_target_resolution_blocks_stale_source_snapshot() -> None:
    payload = _resolve_payload(_signature(), _fresh_snapshot("snap_source"))

    _assert_blocked(payload, "target_resolution_stale_source_snapshot")


def test_target_resolution_blocks_device_mismatch() -> None:
    payload = _resolve_payload(_signature(), _fresh_snapshot("snap_fresh", "other"))

    _assert_blocked(payload, "target_resolution_device_mismatch")


def test_target_resolution_blocks_no_match() -> None:
    payload = _resolve_payload(
        _signature(),
        _snapshot(
            "snap_fresh",
            (
                _element(
                    1,
                    SemanticRole.BUTTON,
                    True,
                    True,
                    "Cancel",
                    "content_desc",
                ),
            ),
        ),
    )

    _assert_blocked(payload, "target_resolution_no_match")
    assert cast(dict[str, object], payload["match"])["candidate_count"] == 0


def test_target_resolution_blocks_ambiguous_match() -> None:
    payload = _resolve_payload(
        _signature(),
        _snapshot("snap_fresh", (_save_element(1), _save_element(2))),
    )

    _assert_blocked(payload, "target_resolution_ambiguous")
    assert cast(dict[str, object], payload["match"])["candidate_count"] == 2


def test_target_resolution_blocks_disabled_match() -> None:
    payload = _resolve_payload(
        _signature(),
        _snapshot("snap_fresh", (_save_element(1, enabled=False),)),
    )

    _assert_blocked(payload, "target_resolution_disabled")


def test_target_resolution_blocks_non_clickable_match() -> None:
    payload = _resolve_payload(
        _signature(),
        _snapshot("snap_fresh", (_save_element(1, clickable=False),)),
    )

    _assert_blocked(payload, "target_resolution_not_clickable")


def test_target_resolution_resolves_non_clickable_input_match() -> None:
    source = build_snapshot_targets(
        _snapshot(
            "snap_source",
            (_element(1, SemanticRole.INPUT, True, False, None, "none"),),
        ),
    )
    signature = build_target_signature(source, "e001")

    payload = _resolve_payload(
        signature,
        _snapshot(
            "snap_fresh",
            (_element(2, SemanticRole.INPUT, True, False, None, "none"),),
        ),
    )

    assert payload["ok"] is True
    target = cast(dict[str, object], payload["resolved_target"])
    assert target["clickable"] is False
    assert target["role"] == "input"


def test_target_resolution_adds_signature_role_to_matching_identity() -> None:
    source = build_snapshot_targets(
        _snapshot(
            "snap_source",
            (_element(1, SemanticRole.INPUT, True, False, None, "none"),),
        ),
    )
    signature = replace(
        build_target_signature(source, "e001"),
        identity={"class_name": "android.widget.Button"},
    )

    payload = _resolve_payload(
        signature,
        _snapshot(
            "snap_fresh",
            (
                _element(
                    2,
                    SemanticRole.BUTTON,
                    True,
                    False,
                    None,
                    "none",
                    class_name="android.widget.Button",
                ),
            ),
        ),
    )

    _assert_blocked(payload, "target_resolution_no_match")


def test_target_resolution_rejects_signature_role_identity_mismatch() -> None:
    signature = replace(
        _signature(),
        role=SemanticRole.INPUT,
        identity={"role": "button", "resource_id": "com.example:id/save"},
    )

    payload = _resolve_payload(signature, _fresh_snapshot("snap_fresh"))

    _assert_blocked(payload, "target_resolution_invalid_signature")


def test_target_resolution_role_only_identity_resolves_when_unique() -> None:
    source = build_snapshot_targets(
        _snapshot(
            "snap_source",
            (_element(1, SemanticRole.INPUT, True, False, None, "none"),),
        ),
    )
    signature = build_target_signature(source, "e001")

    payload = _resolve_payload(
        signature,
        _snapshot(
            "snap_fresh",
            (
                _save_element(1),
                _element(2, SemanticRole.INPUT, True, True, None, "none"),
            ),
        ),
    )

    assert payload["ok"] is True
    assert payload["status"] == "resolved"
    assert payload["match"] == {
        "identity_strength": "weak",
        "matched_fields": ["role"],
        "candidate_count": 1,
    }


def test_target_resolution_role_only_identity_blocks_when_ambiguous() -> None:
    source = build_snapshot_targets(
        _snapshot(
            "snap_source",
            (_element(1, SemanticRole.INPUT, True, False, None, "none"),),
        ),
    )
    signature = build_target_signature(source, "e001")

    payload = _resolve_payload(
        signature,
        _snapshot(
            "snap_fresh",
            (
                _element(2, SemanticRole.INPUT, True, True, None, "none"),
                _element(3, SemanticRole.INPUT, True, True, None, "none"),
            ),
        ),
    )

    _assert_blocked(payload, "target_resolution_ambiguous")


def test_target_resolution_blocks_invalid_signature_schema() -> None:
    payload = _resolve_payload(
        replace(_signature(), schema_version="future.signature.v2"),
        _fresh_snapshot("snap_fresh"),
    )

    _assert_blocked(payload, "target_resolution_invalid_signature")


def test_target_resolution_blocks_invalid_snapshot_schema() -> None:
    payload = _resolve_payload(
        _signature(),
        replace(_fresh_snapshot("snap_fresh"), schema_version="future.snapshot.v2"),
    )

    _assert_blocked(payload, "target_resolution_invalid_snapshot")


def test_target_resolution_blocks_forbidden_fresh_ref_names() -> None:
    fresh = _fresh_snapshot("snap_fresh")
    refs = dict(fresh.refs)
    refs["latest_snapshot_ref"] = _ref("latest.json")

    payload = _resolve_payload(_signature(), replace(fresh, refs=refs))

    _assert_blocked(payload, "target_resolution_invalid_snapshot")
    assert payload["refs"] == {}


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


def _fresh_snapshot(
    snapshot_id: str,
    device_id: str = "RFCN4010FCK",
) -> SemanticSnapshot:
    return _snapshot(snapshot_id, (_save_element(1),), device_id=device_id)


def _snapshot(
    snapshot_id: str,
    elements: tuple[SemanticElement, ...],
    *,
    device_id: str = "RFCN4010FCK",
) -> SemanticSnapshot:
    return SemanticSnapshot(
        schema_version=SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        device_id=device_id,
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
    enabled: bool = True,
    clickable: bool = True,
) -> SemanticElement:
    return SemanticElement(
        source_index=source_index,
        role=SemanticRole.BUTTON,
        bounds=bounds or _bounds(),
        enabled=enabled,
        clickable=clickable,
        label="Save",
        label_source="content_desc",
        class_name="android.widget.Button",
        resource_id="com.example:id/save",
        package="com.example",
    )


def _element(
    source_index: int,
    role: SemanticRole,
    enabled: bool,
    clickable: bool,
    label: str | None,
    label_source: str,
    *,
    class_name: str | None = None,
    resource_id: str | None = None,
    package: str | None = None,
) -> SemanticElement:
    return SemanticElement(
        source_index=source_index,
        role=role,
        bounds=_bounds(),
        enabled=enabled,
        clickable=clickable,
        label=label,
        label_source=label_source,
        class_name=class_name,
        resource_id=resource_id,
        package=package,
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


def _ref(path: str) -> SnapshotArtifactRef:
    return SnapshotArtifactRef(path=path, sha256=f"{path}-sha", byte_length=1)


def _bounds() -> SnapshotBounds:
    return SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0)
