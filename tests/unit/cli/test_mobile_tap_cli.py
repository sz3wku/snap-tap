from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

import typer
from typer.testing import CliRunner

from snap_tap.cli.mobile.app import MobileDependencies, build_mobile_app
from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.contracts import DriverAppAwareness
from snap_tap.backends.contracts import DriverHealth
from snap_tap.backends.contracts import DriverLifecycleResult
from snap_tap.backends.contracts import DriverScreenshot
from snap_tap.backends.contracts import DriverTap
from snap_tap.backends.contracts import DriverXmlDump
from snap_tap.primitives import PrimitiveReceipt, PrimitiveSnapshotResult, PrimitiveTapRequest
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
from snap_tap.targets import latest_snap_source_path


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"
XML_TEXT = """
<hierarchy>
  <node class="android.widget.EditText" resource-id="com.example:id/caption_input"
        package="com.example" bounds="[10,20][210,120]"
        visible-to-user="true" enabled="true" clickable="false"
        scrollable="false" text="Caption" />
  <node class="android.widget.Button" resource-id="com.example:id/save"
        package="com.example" bounds="[220,20][420,120]"
        visible-to-user="true" enabled="true" clickable="true"
        scrollable="false" content-desc="Save" />
  <node class="android.widget.ScrollView" resource-id="com.example:id/list"
        package="com.example" bounds="[0,140][1080,2200]"
        visible-to-user="true" enabled="true" clickable="false"
        scrollable="true" />
</hierarchy>
"""


class FakeDiscovery:
    def __init__(self, devices: Sequence[DeviceInfo]) -> None:
        self._devices = tuple(devices)

    def list_devices(self) -> Sequence[DeviceInfo]:
        return self._devices


class FakeBackend:
    backend_name = "fake"

    def health(self, device_id: str, timeout_s: float = 5.0) -> DriverHealth:
        return DriverHealth.success(
            device_id=device_id,
            backend="fake",
            elapsed_ms=1.0,
        )


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

    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        self.calls.append((device_id, timeout_s))
        return DriverXmlDump.success(
            device_id=device_id,
            backend="fake",
            elapsed_ms=1.0,
            xml=XML_TEXT,
        )


class FakeScreenshotCapturer:
    backend_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []

    def capture(self, device_id: str, timeout_s: float = 10.0) -> DriverScreenshot:
        self.calls.append((device_id, timeout_s))
        return DriverScreenshot.success(
            device_id=device_id,
            backend="fake",
            elapsed_ms=1.0,
            image_bytes=PNG_BYTES,
            metadata={"format": "png", "width": 1080, "height": 2400},
        )


class FakeAppReader:
    backend_name = "fake"

    def app_current(
        self,
        device_id: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness:
        return DriverAppAwareness.success(
            device_id=device_id,
            backend="fake",
            operation="app_current",
            elapsed_ms=1.0,
            metadata={"package": "com.example", "activity": ".Main", "pid": 7},
        )

    def package_info(
        self,
        device_id: str,
        package: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness:
        raise AssertionError("tap tests must not call package_info")


class FakeExecutor:
    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.calls: list[PrimitiveTapRequest] = []

    def tap(self, request: PrimitiveTapRequest) -> PrimitiveReceipt:
        from snap_tap.primitives import resolved_tap

        self.calls.append(request)
        provider = _Provider(self.mode)
        return resolved_tap(
            request,
            snapshot_provider=provider,
            tapper=_Tapper(),
        )


class _Provider:
    def __init__(self, mode: str) -> None:
        if mode == "success":
            self.results = [_snapshot_result("fresh"), _snapshot_result("after")]
        elif mode == "stale":
            self.results = [
                _snapshot_result(
                    "fresh",
                    bounds=SnapshotBounds(900, 900, 1000, 1000, 100, 100, 950.0, 950.0),
                )
            ]
        else:
            self.results = [_snapshot_result("fresh", label="Other")]

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        return self.results.pop(0)


class _Tapper:
    backend_name = "fake"

    def tap(
        self,
        *,
        device_id: str,
        x: float,
        y: float,
        timeout_s: float = 10.0,
    ) -> DriverTap:
        return DriverTap(
            ok=True,
            status="completed",
            device_id=device_id,
            backend="fake",
            operation="tap",
            elapsed_ms=1.0,
            attempted=True,
            confirmed=True,
            checked_at=utc_now(),
        )


def test_mobile_snap_then_tap_id_builds_signature_for_executor(
    tmp_path: Path,
) -> None:
    executor = FakeExecutor()
    app, _xml_dumper = _build_app(tmp_path, executor)
    runner = CliRunner()

    snap = runner.invoke(
        app,
        ["snap", "--device", "RFCN4010FCK", "--session", "default"],
    )
    tap = runner.invoke(
        app,
        ["tap", "e002", "--device", "RFCN4010FCK", "--session", "default", "--json"],
    )

    assert snap.exit_code == 0
    assert tap.exit_code == 0
    payload = _json(tap.stdout)
    assert payload["schema_version"] == "primitive_receipt.v1"
    assert payload["ok"] is True
    assert len(executor.calls) == 1
    request = executor.calls[0]
    assert request.signature.schema_version == "target_signature.v1"
    assert request.signature.display_id == "e002"
    assert request.signature.source_snapshot_id != "fresh"
    assert request.signature.refs == {}


def test_mobile_tap_missing_source_blocks_before_phone_work(tmp_path: Path) -> None:
    executor = FakeExecutor()
    app, xml_dumper = _build_app(tmp_path, executor)

    result = CliRunner().invoke(
        app,
        ["tap", "e002", "--device", "RFCN4010FCK", "--json"],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["error"]["code"] == "latest_snap_source_missing"
    assert payload["attempted_touch"] is False
    assert xml_dumper.calls == []
    assert executor.calls == []


def test_mobile_tap_rejects_corrupt_source_before_phone_work(tmp_path: Path) -> None:
    path = latest_snap_source_path(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    executor = FakeExecutor()
    app, xml_dumper = _build_app(tmp_path, executor)

    result = CliRunner().invoke(
        app,
        ["tap", "e002", "--device", "RFCN4010FCK", "--json"],
    )

    assert result.exit_code == 1
    assert _json(result.stdout)["error"]["code"] == "latest_snap_source_invalid"
    assert xml_dumper.calls == []
    assert executor.calls == []


def test_mobile_tap_rejects_malformed_or_unsafe_id_before_phone_work(
    tmp_path: Path,
) -> None:
    executor = FakeExecutor()
    app, xml_dumper = _build_app(tmp_path, executor)
    runner = CliRunner()
    assert runner.invoke(app, ["snap", "--device", "RFCN4010FCK"]).exit_code == 0
    xml_dumper.calls.clear()

    malformed = runner.invoke(
        app,
        ["tap", "save", "--device", "RFCN4010FCK", "--json"],
    )
    input_target = runner.invoke(
        app,
        ["tap", "e001", "--device", "RFCN4010FCK", "--json"],
    )
    scroll_target = runner.invoke(
        app,
        ["tap", "e003", "--device", "RFCN4010FCK", "--json"],
    )

    assert malformed.exit_code == 1
    assert input_target.exit_code == 1
    assert scroll_target.exit_code == 1
    assert _json(malformed.stdout)["error"]["code"] == "primitive_invalid_request"
    assert _json(input_target.stdout)["error"]["code"] == (
        "latest_snap_source_target_not_tappable"
    )
    assert _json(scroll_target.stdout)["error"]["code"] == (
        "latest_snap_source_target_not_tappable"
    )
    assert xml_dumper.calls == []
    assert executor.calls == []


def test_mobile_tap_preserves_resolution_and_stale_receipts(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    resolution_executor = FakeExecutor("resolution")
    resolution_app, _xml_dumper = _build_app(tmp_path / "resolution", resolution_executor)
    assert runner.invoke(
        resolution_app,
        ["snap", "--device", "RFCN4010FCK"],
    ).exit_code == 0
    resolution = runner.invoke(
        resolution_app,
        ["tap", "e002", "--device", "RFCN4010FCK", "--json"],
    )

    stale_executor = FakeExecutor("stale")
    stale_app, _xml_dumper = _build_app(tmp_path / "stale", stale_executor)
    assert runner.invoke(stale_app, ["snap", "--device", "RFCN4010FCK"]).exit_code == 0
    stale = runner.invoke(
        stale_app,
        ["tap", "e002", "--device", "RFCN4010FCK", "--json"],
    )

    assert resolution.exit_code == 1
    assert _json(resolution.stdout)["blocking_reason"]["code"] == (
        "primitive_resolution_blocked"
    )
    stale_payload = _json(stale.stdout)
    assert stale.exit_code == 1
    assert stale_payload["blocking_reason"]["code"] == "primitive_target_stale"
    assert stale_payload["attempted_touch"] is False
    assert stale_payload["touched_phone"] is False


def test_mobile_tap_custom_sessions_are_isolated(tmp_path: Path) -> None:
    executor = FakeExecutor()
    app, _xml_dumper = _build_app(tmp_path, executor)
    runner = CliRunner()

    snap = runner.invoke(
        app,
        ["snap", "--device", "RFCN4010FCK", "--session", "custom"],
    )
    default_tap = runner.invoke(
        app,
        ["tap", "e002", "--device", "RFCN4010FCK", "--session", "default", "--json"],
    )
    custom_tap = runner.invoke(
        app,
        ["tap", "e002", "--device", "RFCN4010FCK", "--session", "custom", "--json"],
    )

    assert snap.exit_code == 0
    assert default_tap.exit_code == 1
    assert _json(default_tap.stdout)["error"]["code"] == "latest_snap_source_missing"
    assert custom_tap.exit_code == 0


def _build_app(
    cache_root: Path,
    executor: FakeExecutor,
) -> tuple[typer.Typer, FakeXmlDumper]:
    xml_dumper = FakeXmlDumper()
    app = build_mobile_app(
        MobileDependencies(
            discovery=FakeDiscovery([DeviceInfo("RFCN4010FCK", "device")]),
            backend=FakeBackend(),
            lifecycle_runner=FakeLifecycleRunner(),
            xml_dumper=xml_dumper,
            screenshot_capturer=FakeScreenshotCapturer(),
            app_reader=FakeAppReader(),
            primitive_tap_executor=executor,
            latest_cache_root=cache_root,
        )
    )
    return app, xml_dumper


def _snapshot_result(
    snapshot_id: str,
    *,
    label: str = "Save",
    bounds: SnapshotBounds | None = None,
) -> PrimitiveSnapshotResult:
    snapshot = _snapshot(snapshot_id, label=label, bounds=bounds)
    return PrimitiveSnapshotResult(
        ok=True,
        status="completed",
        device_id=snapshot.device_id,
        checked_at=snapshot.captured_at,
        elapsed_ms=1.0,
        snapshot=snapshot,
    )


def _snapshot(
    snapshot_id: str,
    *,
    label: str,
    bounds: SnapshotBounds | None,
) -> SemanticSnapshot:
    element = SemanticElement(
        source_index=2,
        role=SemanticRole.BUTTON,
        bounds=bounds or SnapshotBounds(220, 20, 420, 120, 200, 100, 320.0, 70.0),
        enabled=True,
        clickable=True,
        scrollable=False,
        label=label,
        label_source="content_desc",
        class_name="android.widget.Button",
        resource_id="com.example:id/save",
        package="com.example",
    )
    return SemanticSnapshot(
        schema_version=SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        device_id="RFCN4010FCK",
        captured_at="2026-06-14T10:01:00+00:00",
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
