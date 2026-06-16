from __future__ import annotations

from collections.abc import Sequence
import json
from typing import Any

import typer
from typer.testing import CliRunner

from snap_tap.cli.mobile.app import MobileDependencies, build_mobile_app
from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.contracts import DriverHealth
from snap_tap.backends.contracts import DriverLifecycleResult
from snap_tap.backends.contracts import DriverNavigation
from snap_tap.backends.android.uiautomator2.navigation import NAVIGATION_BACK, NAVIGATION_SWIPE
from snap_tap.backends.contracts import DriverScreenshot
from snap_tap.backends.contracts import DriverXmlDump
from snap_tap.primitives import (
    PrimitiveNavigationRequest,
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
    navigation_primitive,
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
from snap_tap.snapshots import SnapshotArtifactRef, SnapshotBounds


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
        raise AssertionError("primitive navigation CLI tests must not dump XML")


class FakeScreenshotCapturer:
    backend_name = "fake"

    def capture(self, device_id: str, timeout_s: float = 10.0) -> DriverScreenshot:
        raise AssertionError("primitive navigation CLI tests must not capture screenshots")


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[PrimitiveNavigationRequest] = []

    def run(self, request: PrimitiveNavigationRequest) -> PrimitiveReceipt:
        self.calls.append(request)
        return navigation_primitive(
            request,
            snapshot_provider=_Provider(
                [fake_snapshot_result("before"), fake_snapshot_result("after")]
            ),
            navigator=_Navigator(_driver_result(request.operation)),
        )


class _Provider:
    def __init__(self, results: list[PrimitiveSnapshotResult]) -> None:
        self.results = results

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        return self.results.pop(0)


class _Navigator:
    backend_name = "fake"

    def __init__(self, result: DriverNavigation) -> None:
        self.result = result

    def back(self, *, device_id: str, timeout_s: float = 10.0) -> DriverNavigation:
        return self.result

    def home(self, *, device_id: str, timeout_s: float = 10.0) -> DriverNavigation:
        return self.result

    def swipe(
        self,
        *,
        device_id: str,
        direction: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration_ms: int,
        distance_ratio: float,
        timeout_s: float = 10.0,
    ) -> DriverNavigation:
        return self.result


def test_primitive_back_success_outputs_receipt_json() -> None:
    executor = FakeExecutor()
    result = CliRunner().invoke(
        _build_app(executor),
        ["primitive-back", "--device", "RFCN4010FCK", "--json"],
    )

    payload = _json(result.stdout)
    assert result.exit_code == 0
    assert payload["schema_version"] == "primitive_receipt.v1"
    assert payload["operation"] == "back"
    assert payload["ok"] is True
    assert len(executor.calls) == 1


def test_primitive_swipe_exposes_direction_only_request() -> None:
    executor = FakeExecutor()
    result = CliRunner().invoke(
        _build_app(executor),
        [
            "primitive-swipe",
            "--device",
            "RFCN4010FCK",
            "--direction",
            "left",
            "--distance-ratio",
            "0.55",
            "--duration-ms",
            "300",
            "--json",
        ],
    )

    payload = _json(result.stdout)
    assert result.exit_code == 0
    assert payload["request"]["direction"] == "left"
    assert payload["request"]["distance_ratio"] == 0.55
    assert "x1" not in result.stdout
    assert executor.calls[0].direction == "left"


def test_primitive_wait_reports_no_touch() -> None:
    executor = FakeExecutor()
    result = CliRunner().invoke(
        _build_app(executor),
        [
            "primitive-wait",
            "--device",
            "RFCN4010FCK",
            "--seconds",
            "0",
            "--json",
        ],
    )

    payload = _json(result.stdout)
    assert result.exit_code == 0
    assert payload["operation"] == "wait"
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False


def test_primitive_navigation_bad_serial_fails_before_executor() -> None:
    executor = FakeExecutor()
    result = CliRunner().invoke(
        _build_app(executor),
        ["primitive-home", "--device", "bad serial", "--json"],
    )

    payload = _json(result.stdout)
    assert result.exit_code == 1
    assert payload["error"]["code"] == "primitive_invalid_request"
    assert executor.calls == []


def test_primitive_swipe_invalid_args_emit_receipt_before_executor() -> None:
    executor = FakeExecutor()
    result = CliRunner().invoke(
        _build_app(executor),
        [
            "primitive-swipe",
            "--device",
            "RFCN4010FCK",
            "--direction",
            "diagonal",
            "--json",
        ],
    )

    payload = _json(result.stdout)
    assert result.exit_code == 1
    assert payload["error"]["code"] == "primitive_invalid_request"
    assert payload["attempted_touch"] is False
    assert executor.calls == []


def test_primitive_navigation_commands_require_device() -> None:
    executor = FakeExecutor()
    result = CliRunner().invoke(_build_app(executor), ["primitive-back", "--json"])

    assert result.exit_code != 0
    assert executor.calls == []


def _build_app(executor: FakeExecutor) -> typer.Typer:
    return build_mobile_app(
        MobileDependencies(
            discovery=FakeDiscovery([DeviceInfo("RFCN4010FCK", "device")]),
            backend=FakeBackend(),
            lifecycle_runner=FakeLifecycleRunner(),
            xml_dumper=FakeXmlDumper(),
            screenshot_capturer=FakeScreenshotCapturer(),
            primitive_navigation_executor=executor,
        )
    )


def _driver_result(operation: str = NAVIGATION_BACK) -> DriverNavigation:
    return DriverNavigation(
        ok=True,
        status="completed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation=operation if operation != "wait" else NAVIGATION_BACK,
        elapsed_ms=1.0,
        attempted=operation != "wait",
        confirmed=operation != "wait",
        checked_at=utc_now(),
        metadata={"direction": "left"} if operation == NAVIGATION_SWIPE else {},
    )


def fake_snapshot_result(snapshot_id: str) -> PrimitiveSnapshotResult:
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
        role=SemanticRole.BUTTON,
        bounds=SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
        enabled=True,
        clickable=True,
        scrollable=False,
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
        refs={"xml": SnapshotArtifactRef("screen.xml", "xml-sha", 123)},
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


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
