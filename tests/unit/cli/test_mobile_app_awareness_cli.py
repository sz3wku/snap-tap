from __future__ import annotations

from collections.abc import Sequence
import json
from typing import Any

import typer
from typer.testing import CliRunner

from snap_tap.cli.mobile.app import MobileDependencies, build_mobile_app
from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.contracts import DriverAppAwareness
from snap_tap.backends.contracts import DriverHealth
from snap_tap.backends.contracts import DriverLifecycleResult
from snap_tap.backends.contracts import DriverScreenshot
from snap_tap.backends.contracts import DriverXmlDump


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
        )


class FakeXmlDumper:
    backend_name = "fake"

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        return DriverXmlDump.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            xml="<hierarchy />",
        )


class FakeScreenshotCapturer:
    backend_name = "fake"

    def capture(
        self,
        device_id: str,
        timeout_s: float = 10.0,
    ) -> DriverScreenshot:
        return DriverScreenshot.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            image_bytes=b"\x89PNG\r\n\x1a\nfake",
            metadata={
                "format": "png",
                "width": 1,
                "height": 1,
                "byte_length": 12,
                "sha256": "fake",
            },
        )


class FakeAppReader:
    backend_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None, float]] = []

    def app_current(
        self,
        device_id: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness:
        self.calls.append(("app_current", device_id, None, timeout_s))
        return DriverAppAwareness.success(
            device_id=device_id,
            backend=self.backend_name,
            operation="app_current",
            elapsed_ms=1.0,
            metadata={
                "package": "com.example.app",
                "activity": ".MainActivity",
                "pid": 123,
                "timeout_s": timeout_s,
                "private": "ignored",
            },
        )

    def package_info(
        self,
        device_id: str,
        package: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness:
        self.calls.append(("package_info", device_id, package, timeout_s))
        return DriverAppAwareness.success(
            device_id=device_id,
            backend=self.backend_name,
            operation="package_info",
            elapsed_ms=1.0,
            metadata={
                "package": package,
                "version_name": "1.2.3",
                "version_code": 42,
                "timeout_s": timeout_s,
                "private": "ignored",
            },
        )


def test_mobile_app_current_auto_selects_single_online_device() -> None:
    app, reader = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(app, ["app-current", "--timeout-s", "3"])

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "app_current"
    assert payload["result"]["device_id"] == "RFCN4010FCK"
    assert payload["result"]["metadata"] == {
        "package": "com.example.app",
        "activity": ".MainActivity",
        "pid": 123,
    }
    assert reader.calls == [("app_current", "RFCN4010FCK", None, 3.0)]


def test_mobile_app_current_all_outputs_results_array() -> None:
    app, reader = _build_app(
        [
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ]
    )

    result = CliRunner().invoke(app, ["app-current", "--all", "--timeout-s", "2"])

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["count"] == 2
    assert [item["device_id"] for item in payload["results"]] == [
        "RFCN4010FCK",
        "R58R502HMSJ",
    ]
    assert reader.calls == [
        ("app_current", "RFCN4010FCK", None, 2.0),
        ("app_current", "R58R502HMSJ", None, 2.0),
    ]


def test_mobile_app_current_rejects_all_with_explicit_device() -> None:
    app, reader = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(
        app,
        ["app-current", "--all", "--device", "RFCN4010FCK"],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "invalid_arguments"
    assert reader.calls == []


def test_mobile_package_info_requires_valid_package_before_reader() -> None:
    for package_args in (["--package", "bad package"], []):
        app, reader = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

        result = CliRunner().invoke(
            app,
            ["package-info", "--device", "RFCN4010FCK", *package_args],
        )

        assert result.exit_code == 1
        payload = _json(result.stdout)
        assert payload["ok"] is False
        assert payload["result"]["error"]["code"] == "app_unavailable"
        assert reader.calls == []


def test_mobile_package_info_outputs_public_metadata_only() -> None:
    app, reader = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(
        app,
        [
            "package-info",
            "--device",
            "RFCN4010FCK",
            "--package",
            "com.example.app",
            "--timeout-s",
            "4",
        ],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "package_info"
    assert payload["result"]["metadata"] == {
        "package": "com.example.app",
        "version_name": "1.2.3",
        "version_code": 42,
    }
    assert reader.calls == [
        ("package_info", "RFCN4010FCK", "com.example.app", 4.0)
    ]


def test_mobile_package_info_all_checks_each_visible_device() -> None:
    app, reader = _build_app(
        [
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ]
    )

    result = CliRunner().invoke(
        app,
        ["package-info", "--all", "--package", "com.example.app"],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["count"] == 2
    assert reader.calls == [
        ("package_info", "RFCN4010FCK", "com.example.app", 5.0),
        ("package_info", "R58R502HMSJ", "com.example.app", 5.0),
    ]


def test_mobile_package_info_multi_device_without_target_fails_closed() -> None:
    devices = [
        DeviceInfo(serial="RFCN4010FCK", state="device"),
        DeviceInfo(serial="R58R502HMSJ", state="device"),
    ]
    app, reader = _build_app(devices)

    result = CliRunner().invoke(app, ["package-info", "--package", "com.example.app"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["result"]["error"]["code"] == "driver_conflict"
    assert reader.calls == []


def _build_app(devices: Sequence[DeviceInfo]) -> tuple[typer.Typer, FakeAppReader]:
    reader = FakeAppReader()
    app = build_mobile_app(
        MobileDependencies(
            discovery=FakeDiscovery(devices),
            backend=FakeBackend(),
            lifecycle_runner=FakeLifecycleRunner(),
            xml_dumper=FakeXmlDumper(),
            screenshot_capturer=FakeScreenshotCapturer(),
            app_reader=reader,
        )
    )
    return app, reader


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
