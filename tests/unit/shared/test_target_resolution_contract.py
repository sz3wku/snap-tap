from __future__ import annotations

import json
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

RESOLUTION_TOP_LEVEL_KEYS = {
    "schema_version",
    "ok",
    "status",
    "signature_id",
    "source_snapshot_id",
    "resolved_snapshot_id",
    "device_id",
    "resolved_target",
    "match",
    "refs",
}
BLOCKED_TOP_LEVEL_KEYS = RESOLUTION_TOP_LEVEL_KEYS - {"resolved_target"} | {
    "blocking_reason"
}
RESOLVED_TARGET_KEYS = {
    "display_id",
    "snapshot_id",
    "semantic_index",
    "source_index",
    "role",
    "bounds",
    "enabled",
    "clickable",
    "scrollable",
    "actionable",
}
FORBIDDEN_KEYS = {
    "latest_snapshot_ref",
    "primitive_receipt",
    "selector",
    "raw_xml",
    "screenshot_bytes",
    "image_bytes",
    "base64",
    "coordinate_click",
    "model_prompt",
    "phone_touch_result",
}
FORBIDDEN_SENTINELS = (
    "latest-cache-secret",
    "receipt-secret",
    "selector-secret",
    "<hierarchy>DO_NOT_LEAK_XML</hierarchy>",
    "DO_NOT_LEAK_IMAGE_BYTES",
    "DO_NOT_LEAK_BASE64",
    "coordinate-click-secret",
    "model-prompt-secret",
    "phone-touch-secret",
)


def test_target_resolution_contract_payload_surface_is_complete() -> None:
    payload = _resolved_payload()

    assert set(payload) == RESOLUTION_TOP_LEVEL_KEYS
    assert payload["schema_version"] == "target_resolution.v1"
    assert payload["ok"] is True
    assert payload["status"] == "resolved"
    assert payload["source_snapshot_id"] == "snap_source"
    assert payload["resolved_snapshot_id"] == "snap_fresh"

    target = cast(dict[str, object], payload["resolved_target"])
    assert set(target) == RESOLVED_TARGET_KEYS
    assert target["display_id"] == "e001"
    assert target["snapshot_id"] == "snap_fresh"

    refs = cast(dict[str, dict[str, object]], payload["refs"])
    assert refs == {
        "xml": {
            "path": "screen.xml",
            "sha256": "xml-sha",
            "byte_length": 123,
            "node_count": 1,
        },
        "screenshot": {
            "path": "screen.png",
            "sha256": "png-sha",
            "byte_length": 456,
            "format": "png",
            "width": 1080,
            "height": 2400,
        },
        "manifest": {
            "path": "manifest.json",
            "sha256": "manifest-sha",
            "byte_length": 789,
            "metadata": {"schema_version": "snapshot_manifest.v1"},
        },
    }


def test_target_resolution_blocked_payload_uses_blocking_reason_only() -> None:
    payload = target_resolution_to_dict(
        resolve_target_signature(_signature(), _snapshot("snap_source"))
    )

    assert set(payload) == BLOCKED_TOP_LEVEL_KEYS
    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    blocking_reason = cast(dict[str, object], payload["blocking_reason"])
    assert blocking_reason["code"] == "target_resolution_stale_source_snapshot"
    assert blocking_reason["touched_phone"] is False


def test_target_resolution_public_json_excludes_forbidden_surface() -> None:
    payload = _resolved_payload()
    encoded = json.dumps(payload, sort_keys=True)

    _assert_forbidden_keys_absent(payload)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in encoded


def _resolved_payload() -> dict[str, object]:
    return target_resolution_to_dict(
        resolve_target_signature(_signature(), _snapshot("snap_fresh"))
    )


def _signature() -> TargetSignature:
    return build_target_signature(
        build_snapshot_targets(_snapshot("snap_source")),
        "e001",
    )


def _snapshot(snapshot_id: str) -> SemanticSnapshot:
    element = SemanticElement(
        source_index=4,
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
    return SemanticSnapshot(
        schema_version=SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        device_id="RFCN4010FCK",
        captured_at="2026-06-14T10:00:00+00:00",
        refs=_refs(),
        elements=(element,),
        screen_metadata=SemanticScreenMetadata(
            schema_version=SEMANTIC_SCREEN_METADATA_SCHEMA_VERSION,
            viewport=SemanticViewport(
                orientation=ViewportOrientation.PORTRAIT,
                width=1080,
                height=2400,
            ),
            counts=SemanticScreenCounts(
                source_element_count=1,
                visible_element_count=1,
                semantic_element_count=1,
                enabled_count=1,
                clickable_count=1,
                actionable_count=1,
                labeled_count=1,
                unknown_count=0,
            ),
        ),
    )


def _refs() -> dict[str, SnapshotArtifactRef]:
    return {
        "xml": SnapshotArtifactRef(
            path="screen.xml",
            sha256="xml-sha",
            byte_length=123,
            metadata={
                "node_count": 1,
                "raw_xml": "<hierarchy>DO_NOT_LEAK_XML</hierarchy>",
            },
        ),
        "screenshot": SnapshotArtifactRef(
            path="screen.png",
            sha256="png-sha",
            byte_length=456,
            metadata={
                "format": "png",
                "width": 1080,
                "height": 2400,
                "image_bytes": "DO_NOT_LEAK_IMAGE_BYTES",
                "base64": "DO_NOT_LEAK_BASE64",
            },
        ),
        "manifest": SnapshotArtifactRef(
            path="manifest.json",
            sha256="manifest-sha",
            byte_length=789,
            metadata={
                "schema_version": "snapshot_manifest.v1",
                "latest_snapshot_ref": "latest-cache-secret",
                "primitive_receipt": "receipt-secret",
                "selector": "selector-secret",
                "coordinate_click": "coordinate-click-secret",
                "model_prompt": "model-prompt-secret",
                "phone_touch_result": "phone-touch-secret",
            },
        ),
    }


def _assert_forbidden_keys_absent(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            assert key not in FORBIDDEN_KEYS
            _assert_forbidden_keys_absent(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_forbidden_keys_absent(nested)
