from __future__ import annotations

import json
from dataclasses import replace
from typing import cast

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

SIGNATURE_TOP_LEVEL_KEYS = {
    "schema_version",
    "signature_id",
    "source_snapshot_id",
    "device_id",
    "captured_at",
    "display_id",
    "semantic_index",
    "source_index",
    "role",
    "identity",
    "source_bounds",
    "requirements",
    "identity_strength",
    "refs",
}
FORBIDDEN_KEYS = {
    "resolver_result",
    "latest_snapshot_ref",
    "primitive_receipt",
    "selector",
    "raw_xml",
    "screenshot_bytes",
    "image_bytes",
    "base64",
    "coordinate_click",
    "model_prompt",
}
FORBIDDEN_SENTINELS = (
    "resolver-result-secret",
    "latest-cache-secret",
    "receipt-secret",
    "selector-secret",
    "<hierarchy>DO_NOT_LEAK_XML</hierarchy>",
    "DO_NOT_LEAK_IMAGE_BYTES",
    "DO_NOT_LEAK_BASE64",
    "coordinate-click-secret",
    "model-prompt-secret",
)


def test_target_signature_contract_payload_surface_is_complete() -> None:
    payload = _signature_payload()

    assert set(payload) == SIGNATURE_TOP_LEVEL_KEYS
    refs = cast(dict[str, dict[str, object]], payload["refs"])
    assert refs["xml"]["node_count"] == 1
    assert refs["screenshot"]["format"] == "png"
    assert refs["manifest"]["metadata"] == {"schema_version": "snapshot_manifest.v1"}


def test_target_signature_public_json_excludes_forbidden_surface() -> None:
    payload = _signature_payload()
    encoded = json.dumps(payload, sort_keys=True)

    _assert_forbidden_keys_absent(payload)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in encoded


def test_target_signature_fails_closed_for_forbidden_source_ref_names() -> None:
    source = _snapshot_targets()
    refs = dict(source.refs)
    refs["latest_snapshot_ref"] = _ref("latest.json")
    refs["selector"] = _ref("selector.json")

    with pytest.raises(TargetSignatureError) as exc_info:
        build_target_signature(replace(source, refs=refs), "e001")

    assert exc_info.value.code == "target_signature_invalid"


def test_target_signature_serializer_rejects_forbidden_ref_names() -> None:
    signature = build_target_signature(_snapshot_targets(), "e001")
    bad_signature = replace(
        signature,
        refs={"primitive_receipt": _ref("receipt.json")},
    )

    with pytest.raises(TargetSignatureError) as exc_info:
        target_signature_to_dict(bad_signature)

    assert exc_info.value.code == "target_signature_invalid"


def _signature_payload() -> dict[str, object]:
    return target_signature_to_dict(
        build_target_signature(_snapshot_targets(), "e001")
    )


def _snapshot_targets() -> SnapshotTargets:
    return SnapshotTargets(
        schema_version="snapshot_targets.v1",
        snapshot_id="snap_targets",
        device_id="RFCN4010FCK",
        captured_at="2026-06-14T10:00:00+00:00",
        source_schema_version="semantic_snapshot.v1",
        refs={
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
                    "resolver_result": "resolver-result-secret",
                    "latest_snapshot_ref": "latest-cache-secret",
                    "primitive_receipt": "receipt-secret",
                    "selector": "selector-secret",
                    "coordinate_click": "coordinate-click-secret",
                    "model_prompt": "model-prompt-secret",
                },
            ),
        },
        targets=(
            SnapshotTarget(
                display_id="e001",
                snapshot_id="snap_targets",
                semantic_index=0,
                source_index=9,
                role=SemanticRole.BUTTON,
                bounds=SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
                enabled=True,
                clickable=True,
                actionable=True,
                label="Save",
                label_source="content_desc",
                class_name="android.widget.Button",
                resource_id="com.example:id/save",
                package="com.example",
            ),
        ),
    )


def _ref(path: str) -> SnapshotArtifactRef:
    return SnapshotArtifactRef(
        path=path,
        sha256=f"{path}-sha",
        byte_length=1,
        metadata={},
    )


def _assert_forbidden_keys_absent(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            assert key not in FORBIDDEN_KEYS
            _assert_forbidden_keys_absent(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_forbidden_keys_absent(nested)
