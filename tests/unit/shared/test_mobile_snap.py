from __future__ import annotations

from typing import cast

from snap_tap.backends.contracts import DriverAppAwareness
from snap_tap.semantics import build_semantic_snapshot
from snap_tap.snapshots import (
    RawSnapshotCapture,
    SnapshotBounds,
    SnapshotElement,
    SnapshotIdentity,
    SnapshotNormalization,
)
from snap_tap.targets import (
    build_mobile_snap,
    build_snapshot_targets,
    build_target_signature,
    mobile_snap_to_dict,
    target_signature_to_dict,
)


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


def test_mobile_snap_snapshot_app_prefers_non_system_package() -> None:
    payload = mobile_snap_to_dict(
        build_mobile_snap(
            _raw_capture(
                elements=(
                    _element(
                        1,
                        "android.widget.TextView",
                        None,
                        text="16:47",
                        clickable=False,
                        package="com.android.systemui",
                    ),
                    _element(
                        2,
                        "android.widget.ImageView",
                        None,
                        text=None,
                        clickable=False,
                        package="com.android.systemui",
                    ),
                    _element(
                        3,
                        "android.widget.Button",
                        "com.example:id/save",
                        text="Save",
                        package="com.example",
                    ),
                )
            ),
            app_current=None,
            session_id="default",
        )
    )

    assert payload["app"] == {
        "status": "snapshot",
        "package": "com.example",
        "activity": None,
        "pid": None,
    }


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


def test_mobile_snap_adds_operator_label_for_unlabeled_clickable_card() -> None:
    payload = mobile_snap_to_dict(
        build_mobile_snap(
            _raw_capture(elements=_operator_label_elements()),
            app_current=None,
            session_id="default",
        ),
        debug=True,
    )

    target = cast(list[dict[str, object]], payload["targets"])[0]
    assert target["id"] == "e001"
    assert target["kind"] == "tap"
    assert target["label"] is None
    assert target["operator_label"] == "Continue with Instagram"
    assert target["operator_label_source"] == "primary_descendant_text"
    assert target["operator_label_confidence"] == "hint"
    candidates = cast(list[dict[str, object]], target["operator_label_candidates"])
    assert [candidate["label"] for candidate in candidates] == [
        "Continue with Instagram",
        "Use phone number",
    ]


def test_mobile_snap_keeps_single_descendant_text_as_hard_label() -> None:
    payload = mobile_snap_to_dict(
        build_mobile_snap(
            _raw_capture(
                elements=(
                    _element(
                        1,
                        "android.view.View",
                        None,
                        text=None,
                        bounds=_bounds_at(100, 100, 500, 180),
                    ),
                    _element(
                        2,
                        "android.widget.TextView",
                        None,
                        text="Continue",
                        clickable=False,
                        depth=1,
                        bounds=_bounds_at(140, 120, 360, 160),
                    ),
                )
            ),
            app_current=None,
            session_id="default",
        ),
        debug=True,
    )

    target = cast(list[dict[str, object]], payload["targets"])[0]
    assert target["label"] == "Continue"
    assert target["label_source"] == "descendant_text"
    assert target["operator_label"] is None
    assert target["operator_label_candidates"] == []


def test_mobile_snap_does_not_operator_label_huge_clickable_container() -> None:
    payload = mobile_snap_to_dict(
        build_mobile_snap(
            _raw_capture(
                elements=(
                    _element(
                        1,
                        "android.view.View",
                        None,
                        text=None,
                        bounds=_bounds_at(0, 0, 1080, 2400),
                    ),
                    _element(
                        2,
                        "android.widget.TextView",
                        None,
                        text="First",
                        clickable=False,
                        depth=1,
                        bounds=_bounds_at(20, 40, 180, 80),
                    ),
                    _element(
                        3,
                        "android.widget.TextView",
                        None,
                        text="Second",
                        clickable=False,
                        depth=1,
                        bounds=_bounds_at(20, 100, 180, 140),
                    ),
                )
            ),
            app_current=None,
            session_id="default",
        )
    )

    target = cast(list[dict[str, object]], payload["targets"])[0]
    assert target["label"] is None
    assert target["operator_label"] is None


def test_mobile_snap_operator_label_payload_debug_boundary() -> None:
    snap = build_mobile_snap(
        _raw_capture(elements=_operator_label_elements()),
        app_current=None,
        session_id="default",
    )

    default_target = cast(
        list[dict[str, object]],
        mobile_snap_to_dict(snap, debug=False)["targets"],
    )[0]
    debug_target = cast(
        list[dict[str, object]],
        mobile_snap_to_dict(snap, debug=True)["targets"],
    )[0]

    assert default_target["operator_label"] == "Continue with Instagram"
    assert "operator_label_candidates" not in default_target
    assert "operator_label_source" not in default_target
    assert debug_target["operator_label_source"] == "primary_descendant_text"
    assert debug_target["operator_label_confidence"] == "hint"
    assert debug_target["operator_label_candidates"]


def test_mobile_snap_operator_label_is_not_target_signature_identity() -> None:
    raw = _raw_capture(elements=_operator_label_elements())
    snap = build_mobile_snap(raw, app_current=None, session_id="default")

    snap_target = snap.targets[0]
    assert snap_target.label is None
    assert snap_target.operator_label == "Continue with Instagram"

    source = build_snapshot_targets(build_semantic_snapshot(raw))
    signature = target_signature_to_dict(build_target_signature(source, "e001"))

    identity = cast(dict[str, str], signature["identity"])
    assert "label" not in identity
    assert "operator_label" not in identity


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


def _operator_label_elements() -> tuple[SnapshotElement, ...]:
    return (
        _element(
            1,
            "android.view.View",
            None,
            text=None,
            bounds=_bounds_at(45, 450, 675, 770),
        ),
        _element(
            2,
            "android.widget.TextView",
            None,
            text="Continue with Instagram",
            clickable=False,
            depth=1,
            bounds=_bounds_at(90, 500, 520, 550),
        ),
        _element(
            3,
            "android.widget.TextView",
            None,
            text="Use phone number",
            clickable=False,
            depth=1,
            bounds=_bounds_at(90, 570, 420, 620),
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
    depth: int = 0,
    bounds: SnapshotBounds | None = None,
    package: str = "com.example",
) -> SnapshotElement:
    return SnapshotElement(
        source_index=source_index,
        depth=depth,
        bounds=bounds or SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
        visible=True,
        enabled=enabled,
        clickable=clickable,
        scrollable=scrollable,
        class_name=class_name,
        resource_id=resource_id,
        package=package,
        text=text,
    )


def _bounds_at(left: int, top: int, right: int, bottom: int) -> SnapshotBounds:
    width = right - left
    height = bottom - top
    return SnapshotBounds(
        left,
        top,
        right,
        bottom,
        width,
        height,
        left + (width / 2),
        top + (height / 2),
    )
