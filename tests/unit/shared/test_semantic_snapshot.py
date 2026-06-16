from __future__ import annotations

import json
from typing import cast

import pytest

from snap_tap.snapshots import (
    RawSnapshotCapture,
    SnapshotArtifactRef,
    SnapshotBounds,
    SnapshotElement,
    SnapshotIdentity,
    SnapshotNormalization,
)


def test_build_semantic_snapshot_filters_visible_elements_and_preserves_order() -> None:
    from snap_tap.semantics.snapshot import (
        build_semantic_snapshot,
        semantic_snapshot_to_dict,
    )

    raw = _raw_capture(
        elements=[
            _element(source_index=7, class_name="android.widget.Button"),
            _element(source_index=3, visible=False, class_name="android.widget.EditText"),
            _element(
                source_index=9,
                class_name="android.widget.EditText",
                resource_id="com.example:id/comment_field",
            ),
            _element(source_index=5, enabled=False, clickable=False),
        ]
    )

    payload = semantic_snapshot_to_dict(build_semantic_snapshot(raw))

    assert payload["schema_version"] == "semantic_snapshot.v1"
    assert payload["snapshot_id"] == "snap_test"
    assert payload["device_id"] == "RFCN4010FCK"
    assert payload["captured_at"] == "2026-06-14T10:00:00+00:00"
    elements = cast(list[dict[str, object]], payload["elements"])
    assert [element["source_index"] for element in elements] == [7, 9, 5]
    assert [element["role"] for element in elements] == [
        "button",
        "input",
        "unknown",
    ]
    assert payload["role_normalization"] == {
        "source_schema_version": "snapshot_elements.v1",
        "source_element_count": 4,
        "visible_element_count": 3,
        "semantic_element_count": 3,
        "role_counts": {
            "button": 1,
            "tab": 0,
            "input": 1,
            "text": 0,
            "image": 0,
            "list_item": 0,
            "unknown": 1,
        },
        "unknown_count": 1,
        "labeled_count": 0,
        "accessibility_field_counts": {
            "text": 0,
            "content_desc": 0,
            "hint": 0,
        },
    }


def test_semantic_snapshot_exports_normalized_labels_by_precedence() -> None:
    from snap_tap.semantics.snapshot import (
        build_semantic_snapshot,
        semantic_snapshot_to_dict,
    )

    long_hint = "h" * 300
    raw = _raw_capture(
        elements=[
            _element(
                source_index=1,
                text=" Visible \n text ",
                content_desc="  Primary\t label  ",
                hint="Fallback",
            ),
            _element(
                source_index=2,
                text="",
                content_desc="   ",
                hint=f" {long_hint} ",
            ),
            _element(source_index=3),
        ]
    )

    payload = semantic_snapshot_to_dict(build_semantic_snapshot(raw))
    elements = cast(list[dict[str, object]], payload["elements"])

    assert elements[0]["label"] == "Primary label"
    assert elements[0]["label_source"] == "content_desc"
    assert elements[0]["accessibility"] == {
        "text": "Visible text",
        "content_desc": "Primary label",
        "hint": "Fallback",
    }
    assert elements[1]["label"] == "h" * 256
    assert elements[1]["label_source"] == "hint"
    assert elements[1]["accessibility"] == {"hint": "h" * 256}
    assert elements[2]["label"] is None
    assert elements[2]["label_source"] == "none"
    assert elements[2]["accessibility"] == {}
    normalization = cast(dict[str, object], payload["role_normalization"])
    assert normalization["labeled_count"] == 2
    assert normalization["accessibility_field_counts"] == {
        "text": 1,
        "content_desc": 1,
        "hint": 2,
    }


def test_semantic_snapshot_labels_unlabeled_clickable_parent_from_child_text() -> None:
    from snap_tap.semantics.snapshot import (
        build_semantic_snapshot,
        semantic_snapshot_to_dict,
    )

    raw = _raw_capture(
        elements=[
            _element(
                source_index=1,
                class_name="android.view.View",
                text=None,
                depth=0,
                bounds=_bounds_at(100, 100, 500, 180),
            ),
            _element(
                source_index=2,
                class_name="android.widget.TextView",
                text=" Włącz ",
                clickable=False,
                depth=1,
                bounds=_bounds_at(240, 120, 360, 160),
            ),
        ]
    )

    payload = semantic_snapshot_to_dict(build_semantic_snapshot(raw))
    elements = cast(list[dict[str, object]], payload["elements"])

    assert elements[0]["label"] == "Włącz"
    assert elements[0]["label_source"] == "descendant_text"
    assert elements[0]["accessibility"] == {}
    assert elements[1]["label"] == "Włącz"
    assert elements[1]["label_source"] == "text"


def test_semantic_snapshot_does_not_guess_parent_label_from_multiple_children() -> None:
    from snap_tap.semantics.snapshot import (
        build_semantic_snapshot,
        semantic_snapshot_to_dict,
    )

    raw = _raw_capture(
        elements=[
            _element(
                source_index=1,
                class_name="android.view.View",
                depth=0,
                bounds=_bounds_at(100, 100, 500, 220),
            ),
            _element(
                source_index=2,
                class_name="android.widget.TextView",
                text="Odinstaluj",
                clickable=False,
                depth=1,
                bounds=_bounds_at(140, 120, 260, 160),
            ),
            _element(
                source_index=3,
                class_name="android.widget.TextView",
                text="Włącz",
                clickable=False,
                depth=1,
                bounds=_bounds_at(300, 120, 380, 160),
            ),
        ]
    )

    payload = semantic_snapshot_to_dict(build_semantic_snapshot(raw))
    elements = cast(list[dict[str, object]], payload["elements"])

    assert elements[0]["label"] is None
    assert elements[0]["label_source"] == "none"


def test_semantic_snapshot_keeps_raw_refs_but_excludes_private_payloads() -> None:
    from snap_tap.semantics.snapshot import (
        build_semantic_snapshot,
        semantic_snapshot_to_dict,
    )

    raw = _raw_capture(
        elements=[_element(source_index=0, class_name="android.widget.TextView")],
        metadata={
            "text": "secret-label",
            "content-desc": "secret-description",
            "hint": "secret-hint",
            "target_id": "e01",
            "target_signature": "sig",
            "primitive_receipt": "receipt",
        },
    )

    payload = semantic_snapshot_to_dict(build_semantic_snapshot(raw))
    encoded = json.dumps(payload, sort_keys=True)
    refs = cast(dict[str, dict[str, object]], payload["refs"])

    assert refs["xml"]["path"] == "screen.xml"
    assert refs["screenshot"]["path"] == "screen.png"
    assert "secret-label" not in encoded
    assert "secret-description" not in encoded
    assert "secret-hint" not in encoded
    assert "content-desc" not in encoded
    assert "target_id" not in encoded
    assert "target_signature" not in encoded
    assert "primitive_receipt" not in encoded
    assert "image_bytes" not in encoded
    assert "image_base64" not in encoded
    assert "base64" not in encoded


def test_semantic_snapshot_is_deterministic_for_same_raw_input() -> None:
    from snap_tap.semantics.snapshot import (
        build_semantic_snapshot,
        semantic_snapshot_to_dict,
    )

    raw = _raw_capture(
        elements=[
            _element(source_index=2, resource_id="com.example:id/profile_tab"),
            _element(source_index=4, resource_id="com.example:id/post_cell"),
        ]
    )

    first = semantic_snapshot_to_dict(build_semantic_snapshot(raw))
    second = semantic_snapshot_to_dict(build_semantic_snapshot(raw))

    assert first == second


def test_semantic_snapshot_fails_closed_without_raw_snapshot_identity() -> None:
    from snap_tap.semantics.snapshot import (
        SemanticSnapshotError,
        build_semantic_snapshot,
    )

    raw = _raw_capture(elements=[]).with_identity(None)  # type: ignore[arg-type]

    with pytest.raises(SemanticSnapshotError) as exc_info:
        build_semantic_snapshot(raw)

    assert exc_info.value.code == "semantic_snapshot_input_invalid"


def _raw_capture(
    *,
    elements: list[SnapshotElement],
    metadata: dict[str, object] | None = None,
) -> RawSnapshotCapture:
    return RawSnapshotCapture(
        ok=True,
        status="completed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation="snapshot_capture",
        checked_at="2026-06-14T10:00:00+00:00",
        elapsed_ms=1.0,
        refs={
            "xml": SnapshotArtifactRef(
                path="screen.xml",
                sha256="xml-sha",
                byte_length=123,
                metadata={"node_count": len(elements), "base64": "do-not-emit"},
            ),
            "screenshot": SnapshotArtifactRef(
                path="screen.png",
                sha256="png-sha",
                byte_length=456,
                metadata={"format": "png", "width": 1080, "height": 2400},
            ),
        },
        identity=SnapshotIdentity(
            snapshot_id="snap_test",
            snapshot_hash="sha256:raw",
            hash_version="raw_snapshot_hash.v1",
        ),
        elements=tuple(elements),
        normalization=SnapshotNormalization(
            schema_version="snapshot_elements.v1",
            status="completed",
            source_node_count=len(elements),
            element_count=len(elements),
            visible_count=sum(1 for element in elements if element.visible),
            enabled_count=sum(1 for element in elements if element.enabled),
            clickable_count=sum(1 for element in elements if element.clickable),
            discarded_count=0,
            invalid_bounds_count=0,
        ),
        metadata=metadata or {},
    )


def _element(
    *,
    source_index: int,
    depth: int = 0,
    visible: bool = True,
    enabled: bool = True,
    clickable: bool = True,
    class_name: str | None = None,
    resource_id: str | None = None,
    text: str | None = None,
    content_desc: str | None = None,
    hint: str | None = None,
    bounds: SnapshotBounds | None = None,
) -> SnapshotElement:
    return SnapshotElement(
        source_index=source_index,
        depth=depth,
        bounds=bounds or _bounds_at(10, 20, 110, 220),
        visible=visible,
        enabled=enabled,
        clickable=clickable,
        class_name=class_name,
        resource_id=resource_id,
        package="com.example",
        text=text,
        content_desc=content_desc,
        hint=hint,
    )


def _bounds_at(left: int, top: int, right: int, bottom: int) -> SnapshotBounds:
    width = right - left
    height = bottom - top
    return SnapshotBounds(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        width=width,
        height=height,
        center_x=left + (width / 2),
        center_y=top + (height / 2),
    )
