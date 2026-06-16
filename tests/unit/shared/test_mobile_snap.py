from __future__ import annotations

from typing import cast

from snap_tap.backends.contracts import DriverAppAwareness
from snap_tap.snapshots import (
    RawSnapshotCapture,
    SnapshotBounds,
    SnapshotElement,
    SnapshotIdentity,
    SnapshotNormalization,
)
from snap_tap.targets import build_mobile_snap, mobile_snap_to_dict


def test_mobile_snap_classifies_visible_targets_and_summary_counts() -> None:
    payload = mobile_snap_to_dict(
        build_mobile_snap(
            _raw_capture(),
            app_current=_app_current(),
            session_id="default",
        )
    )

    assert payload["schema_version"] == "mobile_snap.v1"
    assert payload["ok"] is True
    assert payload["device_id"] == "RFCN4010FCK"
    assert payload["app"] == {
        "status": "current",
        "package": "com.example",
        "activity": ".MainActivity",
        "pid": 123,
    }
    assert payload["viewport"] == {
        "width": 1080,
        "height": 2400,
        "orientation": "portrait",
    }
    assert payload["summary"] == {
        "element_count": 6,
        "target_count": 6,
        "tap_count": 1,
        "scroll_count": 1,
        "input_count": 1,
        "visible_count": 6,
        "enabled_count": 5,
        "clickable_count": 1,
        "scrollable_count": 1,
    }
    targets = cast(list[dict[str, object]], payload["targets"])
    assert [(target["id"], target["kind"]) for target in targets] == [
        ("e001", "input"),
        ("e002", "tap"),
        ("e003", "scroll"),
        ("e004", "text"),
        ("e005", "image"),
        ("e006", "unknown"),
    ]
    assert targets[0]["actionable"] is True
    assert targets[2]["scrollable"] is True
    assert "source_index" not in targets[0]


def test_mobile_snap_debug_adds_diagnostics_without_raw_payloads() -> None:
    payload = mobile_snap_to_dict(
        build_mobile_snap(
            _raw_capture(),
            app_current=None,
            session_id="default",
        ),
        debug=True,
    )

    encoded = str(payload)
    target = cast(list[dict[str, object]], payload["targets"])[0]
    assert target["source_index"] == 1
    assert target["semantic_index"] == 0
    assert target["class_name"] == "android.widget.EditText"
    assert target["resource_id"] == "com.example:id/caption_input"
    assert target["snapshot_id"] == "snap_mobile"
    assert "<hierarchy" not in encoded
    assert "image_bytes" not in encoded
    assert "base64" not in encoded


def test_mobile_snap_orders_actionable_targets_before_layout_noise() -> None:
    raw = _raw_capture(
        elements=(
            _element(1, None, None, text=None, clickable=False),
            _element(2, "android.widget.Button", "com.example:id/save", text="Save"),
            _element(
                3,
                "android.widget.ScrollView",
                "com.example:id/list",
                text=None,
                clickable=False,
                scrollable=True,
            ),
        )
    )

    payload = mobile_snap_to_dict(
        build_mobile_snap(raw, app_current=None, session_id="default")
    )

    targets = cast(list[dict[str, object]], payload["targets"])
    assert [(target["id"], target["kind"]) for target in targets] == [
        ("e002", "tap"),
        ("e003", "scroll"),
        ("e001", "unknown"),
    ]


def _app_current() -> DriverAppAwareness:
    return DriverAppAwareness.success(
        device_id="RFCN4010FCK",
        backend="fake",
        operation="app_current",
        elapsed_ms=1.0,
        metadata={
            "package": "com.example",
            "activity": ".MainActivity",
            "pid": 123,
        },
    )


def _raw_capture(
    elements: tuple[SnapshotElement, ...] | None = None,
) -> RawSnapshotCapture:
    resolved_elements = elements or (
        _element(
            1,
            "android.widget.EditText",
            "com.example:id/caption_input",
            text="Caption",
            clickable=False,
        ),
        _element(2, "android.widget.Button", "com.example:id/save", text="Save"),
        _element(
            3,
            "android.widget.ScrollView",
            "com.example:id/list",
            text=None,
            clickable=False,
            scrollable=True,
        ),
        _element(4, "android.widget.TextView", "com.example:id/title", text="Title", clickable=False),
        _element(5, "android.widget.ImageView", "com.example:id/photo", text=None, clickable=False),
        _element(6, None, None, text=None, enabled=False, clickable=False),
    )
    return RawSnapshotCapture(
        ok=True,
        status="completed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation="snapshot_capture",
        checked_at="2026-06-14T10:00:00+00:00",
        elapsed_ms=1.0,
        identity=SnapshotIdentity(
            snapshot_id="snap_mobile",
            snapshot_hash="sha256:raw",
            hash_version="raw_snapshot_hash.v1",
        ),
        elements=resolved_elements,
        normalization=SnapshotNormalization(
            schema_version="snapshot_elements.v1",
            status="completed",
            source_node_count=len(resolved_elements),
            element_count=len(resolved_elements),
            visible_count=len(resolved_elements),
            enabled_count=sum(1 for element in resolved_elements if element.enabled),
            clickable_count=sum(1 for element in resolved_elements if element.clickable),
            discarded_count=0,
            invalid_bounds_count=0,
            viewport_width=1080,
            viewport_height=2400,
            scrollable_count=sum(
                1 for element in resolved_elements if element.scrollable
            ),
        ),
    )


def _element(
    source_index: int,
    class_name: str | None,
    resource_id: str | None,
    *,
    text: str | None,
    enabled: bool = True,
    clickable: bool = True,
    scrollable: bool = False,
) -> SnapshotElement:
    return SnapshotElement(
        source_index=source_index,
        depth=0,
        bounds=SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
        visible=True,
        enabled=enabled,
        clickable=clickable,
        scrollable=scrollable,
        class_name=class_name,
        resource_id=resource_id,
        package="com.example",
        text=text,
    )
