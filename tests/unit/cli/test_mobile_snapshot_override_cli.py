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
from snap_tap.backends.contracts import DriverScreenshot
from snap_tap.backends.contracts import DriverXmlDump
from snap_tap.primitives import PrimitiveReceipt, PrimitiveTapRequest, invalid_request_receipt
from snap_tap.snapshots import RawSnapshotCapture, materialize_raw_snapshot_artifacts


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"
XML_TEXT = (
    '<hierarchy><node class="android.widget.Button" '
    'resource-id="com.example:id/save" package="com.example" '
    'bounds="[220,20][420,120]" visible-to-user="true" '
    'enabled="true" clickable="true" content-desc="Save" /></hierarchy>'
)


class FakeDiscovery:
    def __init__(self) -> None:
        self.calls = 0

    def list_devices(self) -> Sequence[DeviceInfo]:
        self.calls += 1
        return [DeviceInfo("RFCN4010FCK", "device")]


class FakeBackend:
    backend_name = "fake"

    def health(self, device_id: str, timeout_s: float = 5.0) -> DriverHealth:
        return DriverHealth.success(
            device_id=device_id,
            backend="fake",
            elapsed_ms=1.0,
            metadata={"timeout_s": timeout_s},
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


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[PrimitiveTapRequest] = []

    def tap(self, request: PrimitiveTapRequest) -> PrimitiveReceipt:
        self.calls.append(request)
        return invalid_request_receipt(
            device_id=request.device_id,
            request={
                "operation": "tap",
                "device_id": request.device_id,
                "signature_id": request.signature.signature_id,
                "source_snapshot_id": request.signature.source_snapshot_id,
            },
            code="primitive_resolution_blocked",
            detail="unit test stops before live primitive execution.",
        )


def test_mobile_snap_snapshot_is_offline_and_does_not_update_latest(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path / "captures")
    app, discovery, xml_dumper, capturer, executor = _build_app(tmp_path / "cache")

    result = CliRunner().invoke(app, ["snap", "--snapshot", str(manifest), "--json"])
    payload = _json(result.stdout)

    assert result.exit_code == 0
    assert payload["schema_version"] == "mobile_snap.v1"
    assert payload["ok"] is True
    assert payload["device_id"] == "RFCN4010FCK"
    assert discovery.calls == 0
    assert xml_dumper.calls == []
    assert capturer.calls == []
    assert executor.calls == []
    assert not any((tmp_path / "cache").glob("*.json"))


def test_mobile_snap_snapshot_rejects_non_default_session_before_phone_work(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path / "captures")
    app, discovery, xml_dumper, _capturer, _executor = _build_app(tmp_path / "cache")

    result = CliRunner().invoke(
        app,
        ["snap", "--snapshot", str(manifest), "--session", "custom", "--json"],
    )
    payload = _json(result.stdout)

    assert result.exit_code == 1
    assert payload["error"]["code"] == "invalid_arguments"
    assert discovery.calls == 0
    assert xml_dumper.calls == []


def test_mobile_tap_snapshot_builds_signature_from_manifest_source(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path / "captures")
    app, discovery, xml_dumper, _capturer, executor = _build_app(tmp_path / "cache")

    result = CliRunner().invoke(
        app,
        ["tap", "e001", "--device", "RFCN4010FCK", "--snapshot", str(manifest), "--json"],
    )

    assert result.exit_code == 1
    assert len(executor.calls) == 1
    request = executor.calls[0]
    assert request.signature.schema_version == "target_signature.v1"
    assert request.signature.display_id == "e001"
    assert set(request.signature.refs) == {"xml", "screenshot", "manifest"}
    assert discovery.calls == 0
    assert xml_dumper.calls == []


def test_mobile_tap_snapshot_blocks_mismatch_before_phone_work(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path / "captures")
    app, discovery, xml_dumper, _capturer, executor = _build_app(tmp_path / "cache")

    result = CliRunner().invoke(
        app,
        ["tap", "e001", "--device", "OTHER", "--snapshot", str(manifest), "--json"],
    )
    payload = _json(result.stdout)

    assert result.exit_code == 1
    assert payload["error"]["code"] == "explicit_snapshot_source_device_mismatch"
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert discovery.calls == 0
    assert xml_dumper.calls == []
    assert executor.calls == []


def test_mobile_tap_snapshot_rejects_non_tap_source_before_phone_work(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path / "captures", clickable=False)
    app, discovery, xml_dumper, _capturer, executor = _build_app(tmp_path / "cache")

    result = CliRunner().invoke(
        app,
        ["tap", "e001", "--device", "RFCN4010FCK", "--snapshot", str(manifest), "--json"],
    )
    payload = _json(result.stdout)

    assert result.exit_code == 1
    assert payload["error"]["code"] == "latest_snap_source_target_not_tappable"
    assert discovery.calls == 0
    assert xml_dumper.calls == []
    assert executor.calls == []


def _build_app(
    cache_root: Path,
) -> tuple[
    typer.Typer,
    FakeDiscovery,
    FakeXmlDumper,
    FakeScreenshotCapturer,
    FakeExecutor,
]:
    executor = FakeExecutor()
    discovery = FakeDiscovery()
    xml_dumper = FakeXmlDumper()
    capturer = FakeScreenshotCapturer()
    deps = MobileDependencies(
        discovery=discovery,
        backend=FakeBackend(),
        lifecycle_runner=FakeLifecycleRunner(),
        xml_dumper=xml_dumper,
        screenshot_capturer=capturer,
        primitive_tap_executor=executor,
        latest_cache_root=cache_root,
    )
    return build_mobile_app(deps), discovery, xml_dumper, capturer, executor


def _capture_manifest(tmp_path: Path, *, clickable: bool = True) -> Path:
    capture = materialize_raw_snapshot_artifacts(
        _raw_capture(clickable=clickable),
        tmp_path,
    )
    assert capture.ok is True
    return Path(capture.refs["manifest"].path)


def _raw_capture(*, clickable: bool) -> RawSnapshotCapture:
    return RawSnapshotCapture.success(
        device_id="RFCN4010FCK",
        backend="fake",
        elapsed_ms=1.0,
        xml=XML_TEXT.replace('clickable="true"', f'clickable="{str(clickable).lower()}"'),
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
