from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import typer
from typer.testing import CliRunner

from snap_tap.backends.contracts import (
    DriverAppCatalog,
    DriverAppEntry,
    DriverAppOpen,
    DriverHealth,
    DriverLifecycleResult,
    DriverScreenshot,
    DriverXmlDump,
)
from snap_tap.cli.mobile.app import MobileDependencies, build_mobile_app
from snap_tap.device.identity import DeviceInfo
from snap_tap.primitives import (
    PrimitiveAppOpenRequest,
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
    app_open_primitive,
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
from snap_tap.snapshots import SnapshotBounds


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
        raise AssertionError("app lifecycle CLI tests must not dump XML")


class FakeScreenshotCapturer:
    backend_name = "fake"

    def capture(self, device_id: str, timeout_s: float = 10.0) -> DriverScreenshot:
        raise AssertionError("app lifecycle CLI tests must not capture screenshots")


class FakeAppLifecycle:
    backend_name = "fake"

    def __init__(self) -> None:
        self.list_calls: list[tuple[str, float]] = []

    def list_launchable_apps(
        self,
        device_id: str,
        timeout_s: float = 5.0,
    ) -> DriverAppCatalog:
        self.list_calls.append((device_id, timeout_s))
        return DriverAppCatalog.success(
            device_id=device_id,
            backend="fake",
            elapsed_ms=1.0,
            apps=[
                DriverAppEntry(
                    package="com.instagram.android",
                    activity=".activity.MainTabActivity",
                ),
                DriverAppEntry(
                    package="com.android.vending",
                    activity=".AssetBrowserActivity",
                ),
            ],
        )

    def open_app(
        self,
        *,
        device_id: str,
        package: str,
        activity: str | None = None,
        timeout_s: float = 10.0,
    ) -> DriverAppOpen:
        return DriverAppOpen(
            ok=True,
            status="completed",
            device_id=device_id,
            backend="fake",
            operation="app_open",
            checked_at=utc_now(),
            elapsed_ms=1.0,
            attempted=True,
            confirmed=True,
            metadata={"package": package, "activity": activity or ""},
        )


class FakeAppOpenExecutor:
    def __init__(self) -> None:
        self.calls: list[PrimitiveAppOpenRequest] = []

    def run(self, request: PrimitiveAppOpenRequest) -> PrimitiveReceipt:
        self.calls.append(request)
        return app_open_primitive(
            request,
            snapshot_provider=_Provider(
                _snapshot_result("after", package=request.package)
            ),
            opener=FakeAppLifecycle(),
        )


class _Provider:
    def __init__(self, result: PrimitiveSnapshotResult) -> None:
        self.result = result

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        return self.result


def test_mobile_apps_outputs_launchable_packages_json() -> None:
    lifecycle = FakeAppLifecycle()
    app = _build_app(app_lifecycle=lifecycle)

    result = CliRunner().invoke(app, ["apps", "RFCN4010FCK", "--json"])

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["count"] == 2
    assert payload["result"]["apps"][0] == {
        "package": "com.instagram.android",
        "activity": ".activity.MainTabActivity",
        "component": "com.instagram.android/.activity.MainTabActivity",
    }
    assert lifecycle.list_calls == [("RFCN4010FCK", 5.0)]


def test_mobile_apps_default_output_is_package_table() -> None:
    app = _build_app(app_lifecycle=FakeAppLifecycle())

    result = CliRunner().invoke(app, ["apps", "RFCN4010FCK"])

    assert result.exit_code == 0
    assert "PACKAGE" in result.stdout
    assert "com.instagram.android" in result.stdout
    assert ".activity.MainTabActivity" in result.stdout


def test_mobile_app_open_package_returns_primitive_result() -> None:
    executor = FakeAppOpenExecutor()
    app = _build_app(app_open_executor=executor)

    result = CliRunner().invoke(
        app,
        ["app-open", "RFCN4010FCK", "com.instagram.android", "--json"],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["schema_version"] == "primitive_result.v1"
    assert payload["operation"] == "app_open"
    assert payload["receipt"]["schema_version"] == "primitive_receipt.v1"
    assert payload["receipt"]["request"]["package"] == "com.instagram.android"
    assert payload["next_snap"]["schema_version"] == "mobile_snap.v1"
    assert [call.package for call in executor.calls] == ["com.instagram.android"]
    assert executor.calls[0].activity is None


def test_mobile_app_open_component_passes_activity_without_resolution() -> None:
    executor = FakeAppOpenExecutor()
    app = _build_app(app_open_executor=executor)

    result = CliRunner().invoke(
        app,
        [
            "app-open",
            "RFCN4010FCK",
            "com.instagram.android/.activity.MainTabActivity",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert executor.calls[0].package == "com.instagram.android"
    assert executor.calls[0].activity == ".activity.MainTabActivity"


def test_mobile_app_open_rejects_plain_alias_before_executor() -> None:
    executor = FakeAppOpenExecutor()
    app = _build_app(app_open_executor=executor)

    result = CliRunner().invoke(app, ["app-open", "RFCN4010FCK", "instagram", "--json"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["schema_version"] == "primitive_result.v1"
    assert payload["receipt"]["error"]["code"] == "app_unavailable"
    assert payload["next_snap"] is None
    assert executor.calls == []


def test_mobile_app_open_rejects_malformed_session_before_executor() -> None:
    executor = FakeAppOpenExecutor()
    app = _build_app(app_open_executor=executor)

    result = CliRunner().invoke(
        app,
        [
            "app-open",
            "RFCN4010FCK",
            "com.instagram.android",
            "--session",
            "../bad",
            "--json",
        ],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["schema_version"] == "primitive_result.v1"
    assert payload["receipt"]["error"]["code"] == "latest_snapshot_ref_invalid"
    assert payload["next_snap"] is None
    assert executor.calls == []


def _build_app(
    *,
    app_lifecycle: FakeAppLifecycle | None = None,
    app_open_executor: FakeAppOpenExecutor | None = None,
    cache_root: Path | None = None,
) -> typer.Typer:
    return build_mobile_app(
        MobileDependencies(
            discovery=FakeDiscovery([DeviceInfo("RFCN4010FCK", "device")]),
            backend=FakeBackend(),
            lifecycle_runner=FakeLifecycleRunner(),
            xml_dumper=FakeXmlDumper(),
            screenshot_capturer=FakeScreenshotCapturer(),
            app_lifecycle=app_lifecycle,
            primitive_app_open_executor=app_open_executor,
            latest_cache_root=cache_root or Path("temp/test-latest"),
        )
    )


def _snapshot_result(
    snapshot_id: str,
    *,
    package: str = "com.example",
) -> PrimitiveSnapshotResult:
    snapshot = _snapshot(snapshot_id, package=package)
    return PrimitiveSnapshotResult(
        ok=True,
        status="completed",
        device_id=snapshot.device_id,
        checked_at=snapshot.captured_at,
        elapsed_ms=1.0,
        snapshot=snapshot,
    )


def _snapshot(snapshot_id: str, *, package: str = "com.example") -> SemanticSnapshot:
    element = SemanticElement(
        source_index=7,
        role=SemanticRole.BUTTON,
        bounds=SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
        enabled=True,
        clickable=True,
        scrollable=False,
        label="Home",
        label_source="content_desc",
        class_name="android.widget.Button",
        resource_id=f"{package}:id/home",
        package=package,
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
            dominant_package=package,
        ),
    )


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
