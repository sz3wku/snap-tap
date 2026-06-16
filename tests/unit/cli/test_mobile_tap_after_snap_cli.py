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
from snap_tap.backends.contracts import DriverError
from snap_tap.backends.contracts import DriverHealth
from snap_tap.backends.contracts import DriverLifecycleResult
from snap_tap.backends.contracts import DriverScreenshot
from snap_tap.backends.contracts import DriverTap
from snap_tap.backends.contracts import DriverXmlDump
from snap_tap.primitives import (
    PrimitiveLeaseManager,
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
    PrimitiveTapRequest,
    resolved_tap,
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
    materialize_raw_snapshot_artifacts,
)
from snap_tap.targets import latest_snap_source_path, read_latest_snap_source


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
</hierarchy>
"""


def test_mobile_tap_default_output_renders_after_snap_table(
    tmp_path: Path,
) -> None:
    app, _xml_dumper = _build_app(tmp_path, _SuccessExecutor())
    runner = CliRunner()

    snap = runner.invoke(
        app,
        ["snap", "--device", "RFCN4010FCK", "--session", "default"],
    )
    tap = runner.invoke(
        app,
        ["tap", "e002", "--device", "RFCN4010FCK", "--session", "default"],
    )

    assert snap.exit_code == 0
    assert tap.exit_code == 0
    assert "RFCN4010FCK  com.example  1080x2400" in tap.stdout
    assert "targets: 1 tap | 0 input | 0 scroll areas | 1 visible" in tap.stdout
    assert "e001" in tap.stdout
    assert "Save" in tap.stdout
    assert "primitive_receipt.v1" not in tap.stdout

    latest = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    assert latest.snapshot.snapshot_id == "after"
    assert [target.display_id for target in latest.targets] == ["e001"]


def test_mobile_tap_json_returns_receipt_and_next_snap(
    tmp_path: Path,
) -> None:
    app, _xml_dumper = _build_app(tmp_path, _SuccessExecutor())
    runner = CliRunner()
    assert runner.invoke(app, ["snap", "--device", "RFCN4010FCK"]).exit_code == 0
    before = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )

    tap = runner.invoke(
        app,
        ["tap", "e002", "--device", "RFCN4010FCK", "--json"],
    )

    assert tap.exit_code == 0
    payload = _json(tap.stdout)
    assert payload["schema_version"] == "primitive_result.v1"
    assert payload["operation"] == "tap"
    assert payload["receipt"]["schema_version"] == "primitive_receipt.v1"
    assert payload["receipt"]["after_snapshot"]["snapshot_id"] == "after"
    assert payload["next_snap"]["schema_version"] == "mobile_snap.v1"
    assert payload["next_snap"]["snapshot"]["snapshot_id"] == "after"
    assert payload["next_snap"]["targets"][0]["label"] == "Save"
    after = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    assert before.snapshot.snapshot_id != "after"
    assert after.snapshot.snapshot_id == "after"


def test_mobile_tap_snapshot_json_returns_next_snap_and_writes_latest_source(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path / "captures")
    app, _xml_dumper = _build_app(tmp_path / "cache", _SuccessExecutor())

    tap = CliRunner().invoke(
        app,
        [
            "tap",
            "e002",
            "--device",
            "RFCN4010FCK",
            "--snapshot",
            str(manifest),
            "--json",
        ],
    )

    assert tap.exit_code == 0
    payload = _json(tap.stdout)
    assert payload["schema_version"] == "primitive_result.v1"
    assert payload["receipt"]["schema_version"] == "primitive_receipt.v1"
    assert payload["receipt"]["after_snapshot"]["snapshot_id"] == "after"
    assert payload["next_snap"]["snapshot"]["snapshot_id"] == "after"
    assert latest_snap_source_path(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path / "cache",
    ).exists()


def test_mobile_tap_failure_with_after_snap_emits_receipt_not_next_table(
    tmp_path: Path,
) -> None:
    app, _xml_dumper = _build_app(tmp_path, _FailingExecutor())
    runner = CliRunner()
    assert runner.invoke(app, ["snap", "--device", "RFCN4010FCK"]).exit_code == 0
    before = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )

    tap = runner.invoke(app, ["tap", "e002", "--device", "RFCN4010FCK"])

    assert tap.exit_code == 1
    payload = _json(tap.stdout)
    assert payload["schema_version"] == "primitive_receipt.v1"
    assert payload["status"] == "failed"
    assert payload["after_snapshot"]["snapshot_id"] == "after"
    assert "targets:" not in tap.stdout
    after = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    assert after.snapshot.snapshot_id == before.snapshot.snapshot_id


def test_mobile_tap_json_failure_includes_receipt_and_next_snap(
    tmp_path: Path,
) -> None:
    app, _xml_dumper = _build_app(tmp_path, _FailingExecutor())
    runner = CliRunner()
    assert runner.invoke(app, ["snap", "--device", "RFCN4010FCK"]).exit_code == 0

    tap = runner.invoke(app, ["tap", "e002", "--device", "RFCN4010FCK", "--json"])

    assert tap.exit_code == 1
    payload = _json(tap.stdout)
    assert payload["schema_version"] == "primitive_result.v1"
    assert payload["ok"] is False
    assert payload["receipt"]["schema_version"] == "primitive_receipt.v1"
    assert payload["receipt"]["status"] == "failed"
    assert payload["receipt"]["after_snapshot"]["snapshot_id"] == "after"
    assert payload["next_snap"]["schema_version"] == "mobile_snap.v1"
    assert payload["next_snap"]["snapshot"]["snapshot_id"] == "after"
    latest = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    assert latest.snapshot.snapshot_id == "after"


class _FakeDiscovery:
    def __init__(self, devices: Sequence[DeviceInfo]) -> None:
        self._devices = tuple(devices)

    def list_devices(self) -> Sequence[DeviceInfo]:
        return self._devices


class _FakeBackend:
    backend_name = "fake"

    def health(self, device_id: str, timeout_s: float = 5.0) -> DriverHealth:
        return DriverHealth.success(
            device_id=device_id,
            backend="fake",
            elapsed_ms=1.0,
        )


class _FakeLifecycleRunner:
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


class _FakeXmlDumper:
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


class _FakeScreenshotCapturer:
    backend_name = "fake"

    def capture(self, device_id: str, timeout_s: float = 10.0) -> DriverScreenshot:
        return DriverScreenshot.success(
            device_id=device_id,
            backend="fake",
            elapsed_ms=1.0,
            image_bytes=PNG_BYTES,
            metadata={"format": "png", "width": 1080, "height": 2400},
        )


class _FakeAppReader:
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
        raise AssertionError("tap after-snap tests must not call package_info")


class _SuccessExecutor:
    def __init__(self) -> None:
        self.calls: list[PrimitiveTapRequest] = []

    def tap(self, request: PrimitiveTapRequest) -> PrimitiveReceipt:
        self.calls.append(request)
        return resolved_tap(
            request,
            snapshot_provider=_Provider(),
            tapper=_SuccessTapper(),
            lease_manager=PrimitiveLeaseManager(in_memory_only=True),
        )


class _FailingExecutor:
    def __init__(self) -> None:
        self.calls: list[PrimitiveTapRequest] = []

    def tap(self, request: PrimitiveTapRequest) -> PrimitiveReceipt:
        self.calls.append(request)
        return resolved_tap(
            request,
            snapshot_provider=_Provider(),
            tapper=_FailingTapper(),
            lease_manager=PrimitiveLeaseManager(in_memory_only=True),
        )


class _Provider:
    def __init__(self) -> None:
        self.results = [_snapshot_result("fresh"), _snapshot_result("after")]

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        return self.results.pop(0)


class _SuccessTapper:
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


class _FailingTapper:
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
            ok=False,
            status="failed",
            device_id=device_id,
            backend="fake",
            operation="tap",
            elapsed_ms=1.0,
            attempted=True,
            confirmed=False,
            checked_at=utc_now(),
            error=DriverError(code="tap_failed", detail="tap failed"),
        )


def _build_app(
    cache_root: Path,
    executor: _SuccessExecutor | _FailingExecutor,
) -> tuple[typer.Typer, _FakeXmlDumper]:
    xml_dumper = _FakeXmlDumper()
    app = build_mobile_app(
        MobileDependencies(
            discovery=_FakeDiscovery([DeviceInfo("RFCN4010FCK", "device")]),
            backend=_FakeBackend(),
            lifecycle_runner=_FakeLifecycleRunner(),
            xml_dumper=xml_dumper,
            screenshot_capturer=_FakeScreenshotCapturer(),
            app_reader=_FakeAppReader(),
            primitive_tap_executor=executor,
            latest_cache_root=cache_root,
        )
    )
    return app, xml_dumper


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
        source_index=2,
        role=SemanticRole.BUTTON,
        bounds=SnapshotBounds(220, 20, 420, 120, 200, 100, 320.0, 70.0),
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


def _capture_manifest(tmp_path: Path) -> Path:
    capture = materialize_raw_snapshot_artifacts(_raw_capture(), tmp_path)
    assert capture.ok is True
    return Path(capture.refs["manifest"].path)


def _raw_capture() -> RawSnapshotCapture:
    return RawSnapshotCapture.success(
        device_id="RFCN4010FCK",
        backend="fake",
        elapsed_ms=1.0,
        xml=XML_TEXT,
        image_bytes=PNG_BYTES,
        metadata={
            "screenshot_format": "png",
            "screenshot_width": 1080,
            "screenshot_height": 2400,
        },
    )


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
