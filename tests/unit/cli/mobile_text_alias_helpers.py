from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

import typer

from snap_tap.cli.mobile.app import MobileDependencies, build_mobile_app
from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.contracts import DriverAppAwareness
from snap_tap.backends.contracts import DriverHealth
from snap_tap.backends.contracts import DriverLifecycleResult
from snap_tap.backends.contracts import DriverScreenshot
from snap_tap.backends.contracts import DriverText
from snap_tap.backends.contracts import DriverXmlDump
from snap_tap.primitives import (
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
    PrimitiveTextRequest,
    resolved_text,
)
from snap_tap.primitives.receipt import utc_now
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
from snap_tap.snapshots import (
    RawSnapshotCapture,
    SnapshotBounds,
    SnapshotElement,
    SnapshotIdentity,
    SnapshotNormalization,
)
from snap_tap.targets import build_latest_snap_source, build_mobile_snap, write_latest_snap_source


class FakeDiscovery:
    def __init__(self, devices: Sequence[DeviceInfo]) -> None:
        self._devices = tuple(devices)

    def list_devices(self) -> Sequence[DeviceInfo]:
        return self._devices


class FakeBackend:
    backend_name = "fake"

    def health(self, device_id: str, timeout_s: float = 5.0) -> DriverHealth:
        return DriverHealth.success(device_id=device_id, backend="fake", elapsed_ms=1.0)


class FakeLifecycleRunner:
    backend_name = "fake"

    def run(
        self,
        *,
        operation: str,
        device_id: str,
        timeout_s: float = 60.0,
    ) -> DriverLifecycleResult:
        return DriverLifecycleResult.success(
            device_id=device_id,
            backend="fake",
            operation=operation,
            elapsed_ms=1.0,
        )


class FakeXmlDumper:
    backend_name = "fake"

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        raise AssertionError("text alias tests must not dump XML before executor")


class FakeScreenshotCapturer:
    backend_name = "fake"

    def capture(self, device_id: str, timeout_s: float = 10.0) -> DriverScreenshot:
        raise AssertionError("text alias tests must not capture screenshots")


class FakeTextExecutor:
    def __init__(self) -> None:
        self.calls: list[PrimitiveTextRequest] = []

    def input_text(self, request: PrimitiveTextRequest) -> PrimitiveReceipt:
        self.calls.append(request)
        return resolved_text(
            request,
            snapshot_provider=_Provider(
                [_snapshot_result("fresh"), _snapshot_result("after")]
            ),
            texter=_Texter(_driver_result(request.mode)),
        )


class _Provider:
    def __init__(self, results: list[PrimitiveSnapshotResult]) -> None:
        self.results = results

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        return self.results.pop(0)


class _Texter:
    backend_name = "fake"

    def __init__(self, result: DriverText) -> None:
        self.result = result

    def input_text(
        self,
        *,
        device_id: str,
        x: float,
        y: float,
        text: str,
        mode: str,
        timeout_s: float = 10.0,
    ) -> DriverText:
        return self.result


def build_text_alias_app(cache_root: Path, executor: FakeTextExecutor) -> typer.Typer:
    return build_mobile_app(
        MobileDependencies(
            discovery=FakeDiscovery([DeviceInfo("RFCN4010FCK", "device")]),
            backend=FakeBackend(),
            lifecycle_runner=FakeLifecycleRunner(),
            xml_dumper=FakeXmlDumper(),
            screenshot_capturer=FakeScreenshotCapturer(),
            primitive_text_executor=executor,
            latest_cache_root=cache_root,
        )
    )


def write_latest_text_source(tmp_path: Path, *, input_target: bool = True) -> None:
    snap = build_mobile_snap(
        _raw_capture(input_target=input_target),
        app_current=_app_current(),
        session_id="default",
    )
    write_latest_snap_source(
        build_latest_snap_source(snap, session_id="default"),
        cache_root=tmp_path,
    )


def json_payload(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload


def _app_current() -> DriverAppAwareness:
    return DriverAppAwareness.success(
        device_id="RFCN4010FCK",
        backend="fake",
        operation="app_current",
        elapsed_ms=1.0,
        metadata={"package": "com.example", "activity": ".Main", "pid": 123},
    )


def _raw_capture(*, input_target: bool) -> RawSnapshotCapture:
    element = SnapshotElement(
        source_index=7,
        depth=0,
        bounds=SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
        visible=True,
        enabled=True,
        clickable=True,
        scrollable=False,
        class_name="android.widget.EditText"
        if input_target
        else "android.widget.Button",
        resource_id="com.example:id/message" if input_target else "com.example:id/save",
        package="com.example",
        hint="Message" if input_target else None,
        content_desc=None if input_target else "Save",
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
        elements=(element,),
        normalization=SnapshotNormalization(
            schema_version="snapshot_elements.v1",
            status="completed",
            source_node_count=1,
            element_count=1,
            visible_count=1,
            enabled_count=1,
            clickable_count=1,
            discarded_count=0,
            invalid_bounds_count=0,
            viewport_width=1080,
            viewport_height=2400,
        ),
    )


def _snapshot_result(snapshot_id: str) -> PrimitiveSnapshotResult:
    snapshot = _snapshot(snapshot_id)
    return PrimitiveSnapshotResult(
        ok=True,
        status="completed",
        device_id=snapshot.device_id,
        checked_at=snapshot.captured_at,
        elapsed_ms=1.0,
        snapshot=snapshot,
    )


def _snapshot(snapshot_id: str) -> SemanticSnapshot:
    element = SemanticElement(
        source_index=7,
        role=SemanticRole.INPUT,
        bounds=SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
        enabled=True,
        clickable=True,
        scrollable=False,
        label="Message",
        label_source="hint",
        class_name="android.widget.EditText",
        resource_id="com.example:id/message",
        package="com.example",
    )
    return SemanticSnapshot(
        schema_version=SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        device_id="RFCN4010FCK",
        captured_at="2026-06-14T10:00:00+00:00",
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


def _driver_result(operation: str) -> DriverText:
    return DriverText(
        ok=True,
        status="completed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation=operation,
        elapsed_ms=1.0,
        attempted=True,
        confirmed=True,
        checked_at=utc_now(),
    )
