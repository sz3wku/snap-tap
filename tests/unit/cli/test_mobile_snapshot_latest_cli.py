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
from snap_tap.snapshots import read_latest_snapshot_ref


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"
XML_TEXT = (
    '<hierarchy><node class="android.widget.Button" '
    'resource-id="com.example:id/ok" package="com.example" '
    'bounds="[10,20][110,220]" visible-to-user="true" '
    'enabled="true" clickable="true" /></hierarchy>'
)


class FakeDiscovery:
    def __init__(self, devices: Sequence[DeviceInfo]) -> None:
        self._devices = list(devices)

    def list_devices(self) -> Sequence[DeviceInfo]:
        return list(self._devices)


class FakeBackend:
    backend_name = "fake"

    def health(self, device_id: str, timeout_s: float = 5.0) -> DriverHealth:
        return DriverHealth.success(
            device_id=device_id,
            backend=self.backend_name,
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
            backend=self.backend_name,
            operation=operation,
            elapsed_ms=1.0,
            metadata={"timeout_s": str(timeout_s)},
        )


class FakeXmlDumper:
    backend_name = "fake"

    def __init__(self, result: DriverXmlDump | None = None) -> None:
        self.calls: list[tuple[str, float]] = []
        self._result = result

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        self.calls.append((device_id, timeout_s))
        if self._result is not None:
            return self._result
        return DriverXmlDump.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            xml=XML_TEXT,
            metadata={"timeout_s": timeout_s},
        )


class FakeScreenshotCapturer:
    backend_name = "fake"

    def __init__(self, result: DriverScreenshot | None = None) -> None:
        self.calls: list[tuple[str, float]] = []
        self._result = result

    def capture(
        self,
        device_id: str,
        timeout_s: float = 10.0,
    ) -> DriverScreenshot:
        self.calls.append((device_id, timeout_s))
        if self._result is not None:
            return self._result
        return DriverScreenshot.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            image_bytes=PNG_BYTES,
            metadata={
                "format": "png",
                "width": 1080,
                "height": 2400,
                "timeout_s": timeout_s,
            },
        )


def test_mobile_snapshot_updates_latest_after_success(tmp_path: Path) -> None:
    cache_root = tmp_path / "latest"
    app, _xml_dumper, _capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        cache_root=cache_root,
    )

    result = CliRunner().invoke(
        app,
        ["snapshot", "RFCN4010FCK", "--out-dir", str(tmp_path / "out")],
    )

    assert result.exit_code == 0
    latest = read_latest_snapshot_ref(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=cache_root,
    )
    payload = _json(result.stdout)
    assert latest.snapshot.snapshot_id == payload["result"]["snapshot_id"]
    assert Path(str(latest.cache["path"])).exists()


def test_mobile_snapshot_custom_session_writes_separate_latest(
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "latest"
    app, _xml_dumper, _capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        cache_root=cache_root,
    )
    runner = CliRunner()

    default = runner.invoke(
        app,
        ["snapshot", "--device", "RFCN4010FCK", "--out-dir", str(tmp_path / "a")],
    )
    custom = runner.invoke(
        app,
        [
            "snapshot",
            "--device",
            "RFCN4010FCK",
            "--out-dir",
            str(tmp_path / "b"),
            "--session",
            "custom",
        ],
    )

    assert default.exit_code == 0
    assert custom.exit_code == 0
    default_latest = read_latest_snapshot_ref(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=cache_root,
    )
    custom_latest = read_latest_snapshot_ref(
        device_id="RFCN4010FCK",
        session_id="custom",
        cache_root=cache_root,
    )
    assert default_latest.cache["path"] != custom_latest.cache["path"]


def test_failed_capture_does_not_update_latest(tmp_path: Path) -> None:
    cache_root = tmp_path / "latest"
    xml_failure = DriverXmlDump.failure(
        backend="fake",
        code="dump_failed",
        detail="blocked",
        device_id="RFCN4010FCK",
        elapsed_ms=1.0,
    )
    app, _xml_dumper, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        cache_root=cache_root,
        xml_dumper=FakeXmlDumper(xml_failure),
    )

    result = CliRunner().invoke(
        app,
        ["snapshot", "--device", "RFCN4010FCK", "--out-dir", str(tmp_path / "out")],
    )

    assert result.exit_code == 1
    assert capturer.calls == []
    assert not cache_root.exists()


def test_mobile_snapshot_latest_emits_json_ref(tmp_path: Path) -> None:
    cache_root = tmp_path / "latest"
    app, _xml_dumper, _capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        cache_root=cache_root,
    )
    runner = CliRunner()
    capture = runner.invoke(
        app,
        ["snapshot", "--device", "RFCN4010FCK", "--out-dir", str(tmp_path / "out")],
    )

    latest = runner.invoke(
        app,
        ["snapshot-latest", "RFCN4010FCK", "--session", "default"],
    )

    assert capture.exit_code == 0
    assert latest.exit_code == 0
    payload = _json(latest.stdout)
    assert payload["ok"] is True
    assert payload["result"]["schema_version"] == "latest_snapshot_ref.v1"
    assert payload["result"]["device_id"] == "RFCN4010FCK"
    assert set(payload["result"]["refs"]) == {"xml", "screenshot", "manifest"}


def test_malformed_session_blocks_before_capture_or_read(
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "latest"
    app, xml_dumper, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        cache_root=cache_root,
    )

    capture = CliRunner().invoke(
        app,
        [
            "snapshot",
            "--device",
            "RFCN4010FCK",
            "--out-dir",
            str(tmp_path / "out"),
            "--session",
            "../bad",
        ],
    )
    latest = CliRunner().invoke(
        app,
        ["snapshot-latest", "--device", "RFCN4010FCK", "--session", "../bad"],
    )

    assert capture.exit_code == 1
    assert latest.exit_code == 1
    assert _json(capture.stdout)["result"]["error"]["code"] == (
        "latest_snapshot_ref_invalid"
    )
    assert _json(latest.stdout)["result"]["error"]["code"] == (
        "latest_snapshot_ref_invalid"
    )
    assert xml_dumper.calls == []
    assert capturer.calls == []
    assert not cache_root.exists()


def test_malformed_device_and_missing_explicit_device_fail_closed(
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "latest"
    app, xml_dumper, capturer = _build_app(
        [
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ],
        cache_root=cache_root,
    )

    malformed = CliRunner().invoke(
        app,
        ["snapshot-latest", "--device", "bad serial"],
    )
    missing = CliRunner().invoke(
        app,
        ["snapshot", "--out-dir", str(tmp_path / "out")],
    )

    assert malformed.exit_code == 1
    assert missing.exit_code == 1
    assert _json(malformed.stdout)["result"]["error"]["code"] == (
        "latest_snapshot_ref_invalid"
    )
    assert _json(missing.stdout)["result"]["error"]["code"] == "device_required"
    assert xml_dumper.calls == []
    assert capturer.calls == []


def _build_app(
    devices: Sequence[DeviceInfo],
    *,
    cache_root: Path,
    xml_dumper: FakeXmlDumper | None = None,
    capturer: FakeScreenshotCapturer | None = None,
) -> tuple[typer.Typer, FakeXmlDumper, FakeScreenshotCapturer]:
    fake_xml_dumper = xml_dumper or FakeXmlDumper()
    fake_capturer = capturer or FakeScreenshotCapturer()
    dependencies = MobileDependencies(
        discovery=FakeDiscovery(devices),
        backend=FakeBackend(),
        lifecycle_runner=FakeLifecycleRunner(),
        xml_dumper=fake_xml_dumper,
        screenshot_capturer=fake_capturer,
        latest_cache_root=cache_root,
    )
    app = build_mobile_app(dependencies)
    return app, fake_xml_dumper, fake_capturer


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
