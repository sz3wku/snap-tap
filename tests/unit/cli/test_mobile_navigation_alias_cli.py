from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

import typer
from typer.testing import CliRunner

from snap_tap.cli.mobile.app import MobileDependencies, build_mobile_app
from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.contracts import DriverHealth
from snap_tap.backends.contracts import DriverLifecycleResult
from snap_tap.backends.contracts import DriverNavigation
from snap_tap.backends.android.uiautomator2.navigation import (
    NAVIGATION_BACK,
    NAVIGATION_HOME,
    NAVIGATION_SWIPE,
)
from snap_tap.backends.contracts import DriverScreenshot
from snap_tap.backends.contracts import DriverXmlDump
from snap_tap.primitives import (
    NAVIGATION_WAIT,
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
from snap_tap.targets import read_latest_snap_source


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
        raise AssertionError("navigation alias tests must not dump XML")


class FakeScreenshotCapturer:
    backend_name = "fake"

    def capture(self, device_id: str, timeout_s: float = 10.0) -> DriverScreenshot:
        raise AssertionError("navigation alias tests must not capture screenshots")


class FakeNavigationExecutor:
    def __init__(self) -> None:
        self.calls: list[PrimitiveNavigationRequest] = []

    def run(self, request: PrimitiveNavigationRequest) -> PrimitiveReceipt:
        self.calls.append(request)
        results = [_snapshot_result("after")]
        if request.operation in {NAVIGATION_SWIPE, NAVIGATION_WAIT}:
            results = [_snapshot_result("before"), _snapshot_result("after")]
        return navigation_primitive(
            request,
            snapshot_provider=_Provider(results),
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


def test_mobile_navigation_aliases_use_primitive_executor_path() -> None:
    executor = FakeNavigationExecutor()
    app = _build_app(executor)
    runner = CliRunner()

    back = runner.invoke(app, ["back", "RFCN4010FCK", "--json"])
    home = runner.invoke(app, ["home", "RFCN4010FCK", "--json"])
    swipe = runner.invoke(
        app,
        ["swipe", "RFCN4010FCK", "--direction", "left", "--json"],
    )
    wait = runner.invoke(
        app,
        ["wait", "RFCN4010FCK", "--seconds", "0", "--json"],
    )

    assert back.exit_code == 0
    assert home.exit_code == 0
    assert swipe.exit_code == 0
    assert wait.exit_code == 0
    assert [_json(item.stdout)["operation"] for item in (back, home, swipe, wait)] == [
        NAVIGATION_BACK,
        NAVIGATION_HOME,
        NAVIGATION_SWIPE,
        NAVIGATION_WAIT,
    ]
    assert [call.operation for call in executor.calls] == [
        NAVIGATION_BACK,
        NAVIGATION_HOME,
        NAVIGATION_SWIPE,
        NAVIGATION_WAIT,
    ]
    assert executor.calls[2].direction == "left"
    assert executor.calls[3].seconds == 0


def test_mobile_navigation_alias_default_output_renders_after_snap_table(
    tmp_path: Path,
) -> None:
    executor = FakeNavigationExecutor()
    app = _build_app(executor, cache_root=tmp_path)

    result = CliRunner().invoke(app, ["back", "RFCN4010FCK"])

    assert result.exit_code == 0
    assert "targets: 1 tap | 0 input | 0 scroll areas | 1 visible" in result.stdout
    assert "e001" in result.stdout
    assert "Save" in result.stdout
    assert "primitive_receipt.v1" not in result.stdout

    latest = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    assert latest.snapshot.snapshot_id == "after"
    assert [target.display_id for target in latest.targets] == ["e001"]


def test_mobile_navigation_alias_invalid_args_fail_before_executor() -> None:
    executor = FakeNavigationExecutor()
    app = _build_app(executor)
    runner = CliRunner()

    bad_serial = runner.invoke(
        app,
        ["back", "--device", "bad serial", "--json"],
    )
    bad_direction = runner.invoke(
        app,
        ["swipe", "--device", "RFCN4010FCK", "--direction", "diagonal", "--json"],
    )
    bad_wait = runner.invoke(
        app,
        ["wait", "--device", "RFCN4010FCK", "--seconds", "-1", "--json"],
    )

    assert bad_serial.exit_code == 1
    assert bad_direction.exit_code == 1
    assert bad_wait.exit_code == 1
    assert _json(bad_serial.stdout)["error"]["code"] == "primitive_invalid_request"
    assert _json(bad_direction.stdout)["error"]["code"] == "primitive_invalid_request"
    assert _json(bad_wait.stdout)["error"]["code"] == "primitive_invalid_request"
    assert executor.calls == []


def test_mobile_navigation_alias_rejects_positional_serial_with_device_option() -> None:
    executor = FakeNavigationExecutor()
    app = _build_app(executor)

    result = CliRunner().invoke(
        app,
        ["back", "RFCN4010FCK", "--device", "RFCN4010FCK", "--json"],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["operation"] == NAVIGATION_BACK
    assert payload["request"]["operation"] == NAVIGATION_BACK
    assert payload["error"]["code"] == "invalid_arguments"
    assert executor.calls == []


def _build_app(
    executor: FakeNavigationExecutor,
    *,
    cache_root: Path | None = None,
) -> typer.Typer:
    dependencies = MobileDependencies(
        discovery=FakeDiscovery([DeviceInfo("RFCN4010FCK", "device")]),
        backend=FakeBackend(),
        lifecycle_runner=FakeLifecycleRunner(),
        xml_dumper=FakeXmlDumper(),
        screenshot_capturer=FakeScreenshotCapturer(),
        primitive_navigation_executor=executor,
    )
    if cache_root is not None:
        dependencies = MobileDependencies(
            discovery=dependencies.discovery,
            backend=dependencies.backend,
            lifecycle_runner=dependencies.lifecycle_runner,
            xml_dumper=dependencies.xml_dumper,
            screenshot_capturer=dependencies.screenshot_capturer,
            primitive_navigation_executor=dependencies.primitive_navigation_executor,
            latest_cache_root=cache_root,
        )
    return build_mobile_app(dependencies)


def _driver_result(operation: str) -> DriverNavigation:
    return DriverNavigation(
        ok=True,
        status="completed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation=operation if operation != NAVIGATION_WAIT else NAVIGATION_BACK,
        elapsed_ms=1.0,
        attempted=operation != NAVIGATION_WAIT,
        confirmed=operation != NAVIGATION_WAIT,
        checked_at=utc_now(),
        metadata={"direction": "left"} if operation == NAVIGATION_SWIPE else {},
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
