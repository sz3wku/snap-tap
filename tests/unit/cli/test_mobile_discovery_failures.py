from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from snap_tap.cli.mobile.app import MobileDependencies, build_mobile_app
from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.contracts import DriverAppAwareness
from snap_tap.backends.contracts import DriverHealth
from snap_tap.backends.contracts import DriverLifecycleResult
from snap_tap.backends.contracts import DriverScreenshot
from snap_tap.backends.contracts import DriverXmlDump


RAW_DISCOVERY_ERROR = "raw adb secret should not leak"


class FailingDiscovery:
    def list_devices(self) -> Sequence[DeviceInfo]:
        raise RuntimeError(RAW_DISCOVERY_ERROR)


class FakeBackend:
    backend_name = "fake"

    def health(self, device_id: str, timeout_s: float = 5.0) -> DriverHealth:
        raise AssertionError("backend should not run after discovery failure")


class FakeLifecycleRunner:
    backend_name = "fake"

    def run(
        self,
        *,
        operation: str,
        device_id: str,
        timeout_s: float = 60.0,
    ) -> DriverLifecycleResult:
        raise AssertionError("lifecycle should not run after discovery failure")


class FakeXmlDumper:
    backend_name = "fake"

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        raise AssertionError("xml dumper should not run after discovery failure")


class FakeScreenshotCapturer:
    backend_name = "fake"

    def capture(
        self,
        device_id: str,
        timeout_s: float = 10.0,
    ) -> DriverScreenshot:
        raise AssertionError("screenshot should not run after discovery failure")


class FakeAppReader:
    backend_name = "fake"

    def app_current(
        self,
        device_id: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness:
        raise AssertionError("app-current should not run after discovery failure")

    def package_info(
        self,
        device_id: str,
        package: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness:
        raise AssertionError("package-info should not run after discovery failure")


def test_mobile_devices_discovery_failure_is_structured_json() -> None:
    result = CliRunner().invoke(_build_app(), ["devices", "--json"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "driver_unavailable"
    assert RAW_DISCOVERY_ERROR not in result.stdout
    assert "Traceback" not in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        ["status", "--device", "RFCN4010FCK"],
        ["status", "--all"],
        ["init", "--device", "RFCN4010FCK"],
        ["doctor", "--device", "RFCN4010FCK"],
        ["dump-xml", "--device", "RFCN4010FCK"],
        ["screenshot", "--device", "RFCN4010FCK", "--out", "screen.png"],
        ["app-current", "--device", "RFCN4010FCK"],
        [
            "package-info",
            "--device",
            "RFCN4010FCK",
            "--package",
            "com.example.app",
        ],
    ],
)
def test_mobile_commands_block_discovery_failure_without_raw_output(
    args: list[str],
    tmp_path: Path,
) -> None:
    normalized_args = [str(tmp_path / arg) if arg == "screen.png" else arg for arg in args]
    if normalized_args[0] == "status":
        normalized_args.append("--json")

    result = CliRunner().invoke(_build_app(), normalized_args)

    assert result.exit_code == 1
    payload = _json(result.stdout)
    error = _first_error(payload)
    assert error["code"] == "driver_unavailable"
    assert error["category"] == "driver"
    assert RAW_DISCOVERY_ERROR not in result.stdout
    assert "Traceback" not in result.stdout


def _build_app() -> typer.Typer:
    return build_mobile_app(
        MobileDependencies(
            discovery=FailingDiscovery(),
            backend=FakeBackend(),
            lifecycle_runner=FakeLifecycleRunner(),
            xml_dumper=FakeXmlDumper(),
            screenshot_capturer=FakeScreenshotCapturer(),
            app_reader=FakeAppReader(),
        )
    )


def _first_error(payload: dict[str, Any]) -> dict[str, Any]:
    if "result" in payload:
        error = payload["result"]["error"]
    else:
        error = payload["results"][0]["error"]
    assert isinstance(error, dict)
    return error


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
