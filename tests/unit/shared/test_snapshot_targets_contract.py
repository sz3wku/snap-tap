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
from snap_tap.targets import build_snapshot_targets, snapshot_targets_to_dict


TARGET_TOP_LEVEL_KEYS = {
    "schema_version",
    "snapshot_id",
    "device_id",
    "captured_at",
    "source_schema_version",
    "refs",
    "targets",
    "summary",
}
TARGET_KEYS = {
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
    "label",
    "label_source",
    "class_name",
    "resource_id",
    "package",
}
FORBIDDEN_KEYS = {
    "target_signature",
    "resolver_result",
    "latest_snapshot_ref",
    "primitive_receipt",
    "selector",
    "raw_xml",
    "screenshot_bytes",
    "image_bytes",
    "base64",
    "model_prompt",
}
FORBIDDEN_SENTINELS = (
    "target-signature-secret",
    "resolver-result-secret",
    "latest-cache-secret",
    "receipt-secret",
    "selector-secret",
    "<hierarchy>DO_NOT_LEAK_XML</hierarchy>",
    "DO_NOT_LEAK_IMAGE_BYTES",
    "DO_NOT_LEAK_BASE64",
    "model-prompt-secret",
)


def test_snapshot_targets_contract_payload_surface_is_complete() -> None:
    payload = _target_payload()

    assert set(payload) == TARGET_TOP_LEVEL_KEYS
    assert payload["schema_version"] == "snapshot_targets.v1"
    assert payload["snapshot_id"] == "snap_targets"
    assert payload["device_id"] == "RFCN4010FCK"
    assert payload["captured_at"] == "2026-06-14T10:00:00+00:00"
    assert payload["source_schema_version"] == "semantic_snapshot.v1"

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


def test_snapshot_target_records_use_only_allowed_public_fields() -> None:
    targets = cast(list[dict[str, object]], _target_payload()["targets"])

    assert len(targets) == 1
    assert set(targets[0]) <= TARGET_KEYS
    assert targets[0]["display_id"] == "e001"
    assert targets[0]["snapshot_id"] == "snap_targets"
    assert targets[0]["role"] == "button"


def test_snapshot_targets_public_json_excludes_forbidden_surface() -> None:
    payload = _target_payload()
    encoded = json.dumps(payload, sort_keys=True)

    _assert_forbidden_keys_absent(payload)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in encoded


def _target_payload() -> dict[str, object]:
    return snapshot_targets_to_dict(build_snapshot_targets(_snapshot()))


def _snapshot() -> SemanticSnapshot:
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
        snapshot_id="snap_targets",
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
                "target_signature": "target-signature-secret",
                "resolver_result": "resolver-result-secret",
                "latest_snapshot_ref": "latest-cache-secret",
                "primitive_receipt": "receipt-secret",
                "selector": "selector-secret",
                "model_prompt": "model-prompt-secret",
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
