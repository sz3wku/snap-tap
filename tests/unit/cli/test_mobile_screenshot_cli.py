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


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"


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
            metadata={"timeout_s": str(timeout_s)},
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

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        return DriverXmlDump.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            xml="<hierarchy />",
            metadata={"timeout_s": str(timeout_s)},
        )


class FakeScreenshotCapturer:
    backend_name = "fake"

    def __init__(
        self,
        ok: bool = True,
        failure_metadata: dict[str, object] | None = None,
    ) -> None:
        self.calls: list[tuple[str, float]] = []
        self._ok = ok
        self._failure_metadata = failure_metadata

    def capture(
        self,
        device_id: str,
        timeout_s: float = 10.0,
    ) -> DriverScreenshot:
        self.calls.append((device_id, timeout_s))
        if not self._ok:
            return DriverScreenshot.failure(
                backend=self.backend_name,
                code="screenshot_failed",
                detail="blocked",
                device_id=device_id,
                elapsed_ms=1.0,
                metadata=self._failure_metadata or {"timeout_s": timeout_s},
            )
        return DriverScreenshot.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            image_bytes=PNG_BYTES,
            metadata={
                "format": "png",
                "width": 1080,
                "height": 2400,
                "byte_length": len(PNG_BYTES),
                "sha256": "abc123",
                "timeout_s": timeout_s,
            },
        )


def test_mobile_screenshot_requires_out_path() -> None:
    app, capturer = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(
        app,
        ["screenshot", "--device", "RFCN4010FCK"],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "invalid_arguments"
    assert capturer.calls == []


def test_mobile_screenshot_blocks_ambiguous_multi_device_selection(
    tmp_path: Path,
) -> None:
    app, capturer = _build_app(
        [
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ]
    )

    result = CliRunner().invoke(
        app,
        ["screenshot", "--out", str(tmp_path / "screen.png")],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "driver_conflict"
    assert capturer.calls == []


def test_mobile_screenshot_blocks_when_no_devices_are_visible(tmp_path: Path) -> None:
    app, capturer = _build_app([])

    result = CliRunner().invoke(
        app,
        ["screenshot", "--out", str(tmp_path / "screen.png")],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "device_offline"
    assert capturer.calls == []


def test_mobile_screenshot_rejects_malformed_serial_before_capture(
    tmp_path: Path,
) -> None:
    app, capturer = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(
        app,
        [
            "screenshot",
            "--device",
            "bad serial",
            "--out",
            str(tmp_path / "screen.png"),
        ],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "device_offline"
    assert capturer.calls == []


def test_mobile_screenshot_writes_png_and_omits_image_bytes(tmp_path: Path) -> None:
    app, capturer = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])
    out = tmp_path / "nested" / "screen.png"

    result = CliRunner().invoke(
        app,
        [
            "screenshot",
            "--device",
            "RFCN4010FCK",
            "--out",
            str(out),
            "--timeout-s",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert out.read_bytes() == PNG_BYTES
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "screenshot"
    assert payload["result"]["path"] == str(out)
    assert payload["result"]["metadata"]["format"] == "png"
    assert payload["result"]["metadata"]["width"] == 1080
    assert payload["result"]["metadata"]["height"] == 2400
    assert payload["result"]["metadata"]["byte_length"] == len(PNG_BYTES)
    assert payload["result"]["metadata"]["sha256"] == "abc123"
    assert "timeout_s" not in payload["result"]["metadata"]
    assert "image_base64" not in result.stdout
    assert "image_bytes" not in result.stdout
    assert capturer.calls == [("RFCN4010FCK", 3.0)]


def test_mobile_screenshot_does_not_write_when_capture_fails(tmp_path: Path) -> None:
    app, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        capturer=FakeScreenshotCapturer(ok=False),
    )
    out = tmp_path / "screen.png"

    result = CliRunner().invoke(
        app,
        ["screenshot", "--device", "RFCN4010FCK", "--out", str(out)],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "screenshot_failed"
    assert not out.exists()
    assert capturer.calls == [("RFCN4010FCK", 10.0)]


def test_mobile_screenshot_omits_hostile_failure_metadata(tmp_path: Path) -> None:
    app, _capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        capturer=FakeScreenshotCapturer(
            ok=False,
            failure_metadata={
                "timeout_s": 10.0,
                "image_base64": "secret-screenshot-bytes",
                "path": "private-path",
            },
        ),
    )

    result = CliRunner().invoke(
        app,
        ["screenshot", "--device", "RFCN4010FCK", "--out", str(tmp_path / "s.png")],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["result"]["metadata"] == {}
    assert "image_base64" not in result.stdout
    assert "secret-screenshot-bytes" not in result.stdout
    assert "private-path" not in result.stdout


def _build_app(
    devices: Sequence[DeviceInfo],
    capturer: FakeScreenshotCapturer | None = None,
) -> tuple[typer.Typer, FakeScreenshotCapturer]:
    screenshot_capturer = capturer or FakeScreenshotCapturer()
    app = build_mobile_app(
        MobileDependencies(
            discovery=FakeDiscovery(devices),
            backend=FakeBackend(),
            lifecycle_runner=FakeLifecycleRunner(),
            xml_dumper=FakeXmlDumper(),
            screenshot_capturer=screenshot_capturer,
        )
    )
    return app, screenshot_capturer


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
