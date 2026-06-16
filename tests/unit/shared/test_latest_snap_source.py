from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from snap_tap.backends.contracts import DriverAppAwareness
from snap_tap.snapshots import (
    RawSnapshotCapture,
    SnapshotBounds,
    SnapshotElement,
    SnapshotIdentity,
    SnapshotNormalization,
)
from snap_tap.targets import (
    LatestSnapSourceError,
    MobileSnap,
    build_latest_snap_source,
    build_mobile_snap,
    build_target_signature,
    latest_snap_source_target_for_input,
    latest_snap_source_path,
    latest_snap_source_target_for_tap,
    latest_snap_source_to_dict,
    read_latest_snap_source,
    snapshot_targets_from_latest_snap_source,
    write_latest_snap_source,
)


FORBIDDEN_SENTINELS = (
    "<hierarchy>DO_NOT_LEAK_XML</hierarchy>",
    "DO_NOT_LEAK_IMAGE_BYTES",
    "DO_NOT_LEAK_BASE64",
    "screen.png",
    "screen.xml",
    "manifest.json",
    "capture-",
    "primitive_receipt",
    "target_resolution",
    "platform_semantics",
    "model_prompt",
)


def test_latest_snap_source_round_trip_is_sanitized(tmp_path: Path) -> None:
    source = build_latest_snap_source(_snap(), session_id="default")
    written = write_latest_snap_source(source, cache_root=tmp_path)

    read_back = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    payload = latest_snap_source_to_dict(written)
    encoded = json.dumps(payload, sort_keys=True)

    assert read_back == written
    assert payload["schema_version"] == "latest_snap_source.v1"
    assert payload["device_id"] == "RFCN4010FCK"
    assert payload["session_id"] == "default"
    assert Path(latest_snap_source_path(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )).exists()
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in encoded


def test_latest_snap_source_rebuilds_target_signature() -> None:
    source = build_latest_snap_source(_snap(), session_id="default")
    target = latest_snap_source_target_for_tap(source, "e001")
    signature = build_target_signature(
        snapshot_targets_from_latest_snap_source(source),
        target.display_id,
    )

    assert signature.schema_version == "target_signature.v1"
    assert signature.device_id == "RFCN4010FCK"
    assert signature.display_id == "e001"
    assert signature.source_snapshot_id == "snap_mobile"
    assert signature.refs == {}


def test_latest_snap_source_read_failures_are_structured(tmp_path: Path) -> None:
    with pytest.raises(LatestSnapSourceError) as missing:
        read_latest_snap_source(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    path = latest_snap_source_path(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(LatestSnapSourceError) as corrupt:
        read_latest_snap_source(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    assert missing.value.code == "latest_snap_source_missing"
    assert corrupt.value.code == "latest_snap_source_invalid"


def test_latest_snap_source_device_and_session_mismatch_fail_closed(
    tmp_path: Path,
) -> None:
    source = write_latest_snap_source(
        build_latest_snap_source(_snap(), session_id="other"),
        cache_root=tmp_path,
    )
    payload = latest_snap_source_to_dict(source)
    path = latest_snap_source_path(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(LatestSnapSourceError) as session:
        read_latest_snap_source(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    payload["device_id"] = "OTHER"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LatestSnapSourceError) as device:
        read_latest_snap_source(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    assert session.value.code == "latest_snap_source_session_mismatch"
    assert device.value.code == "latest_snap_source_device_mismatch"


def test_latest_snap_source_rejects_unsafe_tap_targets() -> None:
    source = build_latest_snap_source(_snap(disabled=True), session_id="default")

    with pytest.raises(LatestSnapSourceError) as disabled:
        latest_snap_source_target_for_tap(source, "e001")
    with pytest.raises(LatestSnapSourceError) as malformed:
        latest_snap_source_target_for_tap(source, "save")

    assert disabled.value.code == "latest_snap_source_target_not_tappable"
    assert malformed.value.code == "latest_snap_source_target_invalid"


def test_latest_snap_source_validates_input_targets() -> None:
    source = build_latest_snap_source(_input_snap(), session_id="default")
    button_source = build_latest_snap_source(_snap(), session_id="default")
    non_clickable = build_latest_snap_source(
        _input_snap(clickable=False),
        session_id="default",
    )

    target = latest_snap_source_target_for_input(source, "e001")
    with pytest.raises(LatestSnapSourceError) as button:
        latest_snap_source_target_for_input(button_source, "e001")
    with pytest.raises(LatestSnapSourceError) as disabled_input:
        latest_snap_source_target_for_input(non_clickable, "e001")

    assert target.display_id == "e001"
    assert button.value.code == "latest_snap_source_target_not_input"
    assert disabled_input.value.code == "latest_snap_source_target_not_input"


def test_latest_snap_source_accepts_existing_long_display_id_shape() -> None:
    source = build_latest_snap_source(_snap(), session_id="default")
    long_target = replace(source.targets[0], display_id="e1000")
    source = replace(source, targets=(long_target,))

    target = latest_snap_source_target_for_tap(source, "e1000")

    assert target.display_id == "e1000"


def test_latest_snap_source_rejects_target_snapshot_id_drift() -> None:
    source = build_latest_snap_source(_snap(), session_id="default")
    drifted = replace(source.targets[0], snapshot_id="other_snapshot")
    source = replace(source, targets=(drifted,))

    with pytest.raises(LatestSnapSourceError) as exc:
        snapshot_targets_from_latest_snap_source(source)

    assert exc.value.code == "latest_snap_source_invalid"


def _snap(*, disabled: bool = False) -> MobileSnap:
    return build_mobile_snap(
        _raw_capture(disabled=disabled),
        app_current=_app_current(),
        session_id="default",
    )


def _input_snap(*, clickable: bool = True) -> MobileSnap:
    return build_mobile_snap(
        _raw_capture(
            class_name="android.widget.EditText",
            resource_id="com.example:id/message",
            content_desc=None,
            hint="Message",
            clickable=clickable,
        ),
        app_current=_app_current(),
        session_id="default",
    )


def _app_current() -> DriverAppAwareness:
    return DriverAppAwareness.success(
        device_id="RFCN4010FCK",
        backend="fake",
        operation="app_current",
        elapsed_ms=1.0,
        metadata={"package": "com.example", "activity": ".Main", "pid": 123},
    )


def _raw_capture(
    *,
    disabled: bool = False,
    class_name: str = "android.widget.Button",
    resource_id: str = "com.example:id/save",
    content_desc: str | None = "Save",
    hint: str | None = None,
    clickable: bool = True,
) -> RawSnapshotCapture:
    element = SnapshotElement(
        source_index=2,
        depth=0,
        bounds=SnapshotBounds(220, 20, 420, 120, 200, 100, 320.0, 70.0),
        visible=True,
        enabled=not disabled,
        clickable=clickable,
        scrollable=False,
        class_name=class_name,
        resource_id=resource_id,
        package="com.example",
        content_desc=content_desc,
        hint=hint,
    )
    elements = (element,)
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
        elements=elements,
        normalization=SnapshotNormalization(
            schema_version="snapshot_elements.v1",
            status="completed",
            source_node_count=len(elements),
            element_count=len(elements),
            visible_count=len(elements),
            enabled_count=0 if disabled else 1,
            clickable_count=1,
            discarded_count=0,
            invalid_bounds_count=0,
            viewport_width=1080,
            viewport_height=2400,
        ),
    )
