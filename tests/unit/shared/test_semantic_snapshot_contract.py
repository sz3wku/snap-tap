from __future__ import annotations

import json
from typing import cast

from snap_tap.semantics.snapshot import (
    build_semantic_snapshot,
    semantic_snapshot_to_dict,
)
from snap_tap.snapshots import (
    RawSnapshotCapture,
    SnapshotArtifactRef,
    SnapshotBounds,
    SnapshotElement,
    SnapshotIdentity,
    SnapshotNormalization,
)

SEMANTIC_TOP_LEVEL_KEYS = {
    "schema_version", "snapshot_id", "device_id", "captured_at",
    "refs", "elements", "screen_metadata", "role_normalization",
}
SEMANTIC_ELEMENT_KEYS = {
    "source_index", "role", "bounds", "enabled", "clickable", "scrollable", "label",
    "label_source", "accessibility", "class_name", "resource_id", "package",
}
FORBIDDEN_KEYS = {
    "raw_xml", "xml_payload", "xml_text", "screenshot_bytes", "image_bytes",
    "image_base64", "base64", "target_id", "target_ids", "target_signature",
    "target_signatures", "selector", "selectors", "primitive_receipt",
    "primitive_receipts", "receipt", "receipts", "latest_snapshot",
    "latest_snapshot_ref", "latest_cache", "cache_ref", "screen_id",
    "screen_title", "screen_hint", "screen_hints", "safe_action",
    "safe_actions", "safe_next_actions", "model_prompt", "prompt",
}
FORBIDDEN_SENTINELS = (
    "<hierarchy>DO_NOT_LEAK_XML</hierarchy>", "DO_NOT_LEAK_IMAGE_BYTES",
    "DO_NOT_LEAK_BASE64", "e01", "target-signature-secret",
    "selector-secret", "receipt-secret", "latest-cache-secret",
    "screen-hint-secret", "safe-action-secret", "model-prompt-secret",
)


def test_semantic_snapshot_contract_payload_surface_is_complete() -> None:
    payload = _semantic_payload()

    assert set(payload) == SEMANTIC_TOP_LEVEL_KEYS
    assert payload["schema_version"] == "semantic_snapshot.v1"
    assert payload["snapshot_id"] == "snap_contract"
    assert payload["device_id"] == "RFCN4010FCK"
    assert payload["captured_at"] == "2026-06-14T10:00:00+00:00"

    refs = cast(dict[str, dict[str, object]], payload["refs"])
    assert set(refs) == {"xml", "screenshot", "manifest"}
    assert refs["xml"] == {
        "path": "screen.xml",
        "sha256": "xml-sha",
        "byte_length": 123,
        "node_count": 5,
    }
    assert refs["screenshot"] == {
        "path": "screen.png",
        "sha256": "png-sha",
        "byte_length": 456,
        "format": "png",
        "width": 1080,
        "height": 2400,
    }
    assert refs["manifest"] == {
        "path": "manifest.json",
        "sha256": "manifest-sha",
        "byte_length": 789,
        "metadata": {"schema_version": "snapshot_manifest.v1"},
    }


def test_semantic_elements_use_allowed_fields_and_raw_visible_order() -> None:
    elements = cast(list[dict[str, object]], _semantic_payload()["elements"])

    assert [element["source_index"] for element in elements] == [5, 9, 7, 11]
    assert [element["role"] for element in elements] == [
        "button",
        "input",
        "text",
        "unknown",
    ]
    assert [
        (element["label"], element["label_source"]) for element in elements
    ] == [("Save", "content_desc"), ("Name", "text"), ("Caption", "hint"), (None, "none")]
    for element in elements:
        assert set(element) <= SEMANTIC_ELEMENT_KEYS
        assert "id" not in element
        assert "target_id" not in element
        assert "target_signature" not in element


def test_semantic_screen_metadata_and_role_normalization_match_contract() -> None:
    payload = _semantic_payload()
    metadata = cast(dict[str, object], payload["screen_metadata"])
    viewport = cast(dict[str, object], metadata["viewport"])
    counts = cast(dict[str, object], metadata["counts"])
    packages = cast(list[dict[str, object]], metadata["packages"])
    normalization = cast(dict[str, object], payload["role_normalization"])

    assert metadata["schema_version"] == "semantic_screen_metadata.v1"
    assert viewport == {"width": 1080, "height": 2400, "orientation": "portrait"}
    assert [
        (
            package["package"],
            package["element_count"],
            package["visible_count"],
            package["semantic_count"],
        )
        for package in packages
    ] == [("com.beta", 2, 2, 2), ("com.alpha", 1, 1, 1), ("com.hidden", 1, 0, 0)]
    assert metadata["dominant_package"] == "com.beta"
    assert counts == {
        "source_element_count": 5,
        "visible_element_count": 4,
        "semantic_element_count": 4,
        "enabled_count": 2,
        "clickable_count": 1,
        "scrollable_count": 0,
        "actionable_count": 1,
        "labeled_count": 3,
        "unknown_count": 1,
    }
    assert normalization["source_schema_version"] == "snapshot_elements.v1"
    assert normalization["source_element_count"] == 5
    assert normalization["visible_element_count"] == 4
    assert normalization["semantic_element_count"] == 4
    assert normalization["role_counts"] == {
        "button": 1,
        "tab": 0,
        "input": 1,
        "text": 1,
        "image": 0,
        "list_item": 0,
        "unknown": 1,
    }
    assert normalization["unknown_count"] == 1
    assert normalization["labeled_count"] == 3
    assert normalization["accessibility_field_counts"] == {
        "text": 1,
        "content_desc": 1,
        "hint": 1,
    }


def test_semantic_snapshot_json_excludes_forbidden_public_surface() -> None:
    payload = _semantic_payload()
    encoded = json.dumps(payload, sort_keys=True)

    _assert_forbidden_keys_absent(payload)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in encoded


def test_semantic_snapshot_contract_output_is_deterministic() -> None:
    raw = _raw_capture()

    first = semantic_snapshot_to_dict(build_semantic_snapshot(raw))
    second = semantic_snapshot_to_dict(build_semantic_snapshot(raw))

    assert first == second


def _semantic_payload() -> dict[str, object]:
    return semantic_snapshot_to_dict(build_semantic_snapshot(_raw_capture()))


def _raw_capture() -> RawSnapshotCapture:
    elements = (
        _element(5, "android.widget.Button", "com.beta:id/save", "com.beta", content_desc=" Save "),
        _element(3, "android.widget.EditText", "com.hidden:id/edit", "com.hidden", visible=False, text="Hidden"),
        _element(9, "android.widget.EditText", "com.alpha:id/name_field", "com.alpha", clickable=False, text=" Name "),
        _element(7, "android.widget.TextView", "com.beta:id/caption", "com.beta", enabled=False, clickable=False, hint=" Caption "),
        _element(11, None, None, None, enabled=False, clickable=False),
    )
    return RawSnapshotCapture(
        ok=True,
        status="completed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation="snapshot_capture",
        checked_at="2026-06-14T10:00:00+00:00",
        elapsed_ms=1.0,
        refs=_refs(len(elements)),
        identity=SnapshotIdentity(
            snapshot_id="snap_contract",
            snapshot_hash="sha256:raw",
            hash_version="raw_snapshot_hash.v1",
        ),
        elements=elements,
        normalization=SnapshotNormalization(
            schema_version="snapshot_elements.v1",
            status="completed",
            source_node_count=len(elements),
            element_count=len(elements),
            visible_count=4,
            enabled_count=2,
            clickable_count=1,
            discarded_count=0,
            invalid_bounds_count=0,
            viewport_width=1080,
            viewport_height=2400,
        ),
        metadata={
            "raw_xml": "<hierarchy>DO_NOT_LEAK_XML</hierarchy>",
            "image_bytes": "DO_NOT_LEAK_IMAGE_BYTES",
            "base64": "DO_NOT_LEAK_BASE64",
            "target_id": "e01",
            "target_signature": "target-signature-secret",
            "selector": "selector-secret",
            "primitive_receipt": "receipt-secret",
            "latest_snapshot_ref": "latest-cache-secret",
            "screen_id": "screen-secret",
            "screen_hint": "screen-hint-secret",
            "safe_next_actions": "safe-action-secret",
            "model_prompt": "model-prompt-secret",
        },
    )


def _refs(node_count: int) -> dict[str, SnapshotArtifactRef]:
    return {
        "xml": SnapshotArtifactRef(
            path="screen.xml",
            sha256="xml-sha",
            byte_length=123,
            metadata={
                "node_count": node_count,
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
            },
        ),
    }


def _element(
    source_index: int,
    class_name: str | None,
    resource_id: str | None,
    package: str | None,
    *,
    visible: bool = True,
    enabled: bool = True,
    clickable: bool = True,
    text: str | None = None,
    content_desc: str | None = None,
    hint: str | None = None,
) -> SnapshotElement:
    return SnapshotElement(
        source_index=source_index,
        depth=0,
        bounds=SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
        visible=visible,
        enabled=enabled,
        clickable=clickable,
        class_name=class_name,
        resource_id=resource_id,
        package=package,
        text=text,
        content_desc=content_desc,
        hint=hint,
    )


def _assert_forbidden_keys_absent(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            assert key not in FORBIDDEN_KEYS
            _assert_forbidden_keys_absent(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_forbidden_keys_absent(nested)
