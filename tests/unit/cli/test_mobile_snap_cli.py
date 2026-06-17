from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import typer
from typer.testing import CliRunner

from snap_tap.backends.contracts import (
    DriverAppAwareness,
    DriverHealth,
    DriverLifecycleResult,
    DriverScreenshot,
    DriverXmlDump,
)
from snap_tap.cli.mobile.app import MobileDependencies, build_mobile_app
from snap_tap.device.identity import DeviceInfo
from snap_tap.targets import read_latest_snap_source

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

XML_OPERATOR_LABEL_TEXT = """
<hierarchy>
  <node class="android.view.View" package="com.example"
        bounds="[45,450][675,770]" visible-to-user="true" enabled="true"
        clickable="true" scrollable="false">
    <node class="android.widget.TextView" package="com.example"
          bounds="[90,500][520,550]" visible-to-user="true" enabled="true"
          clickable="false" scrollable="false"
          text="Kontynuuj przy użyciu Instagramu" />
    <node class="android.widget.TextView" package="com.example"
          bounds="[90,570][420,620]" visible-to-user="true" enabled="true"
          clickable="false" scrollable="false" text="Użyj numeru telefonu" />
  </node>
</hierarchy>
"""


class FakeDiscovery:
    def __init__(self, devices: Sequence[DeviceInfo]) -> None:
        self._devices = list(devices)
        self.calls = 0

    def list_devices(self) -> Sequence[DeviceInfo]:
        self.calls += 1
        return list(self._devices)


class FailingDiscovery:
    calls = 0

    def list_devices(self) -> Sequence[DeviceInfo]:
        self.calls += 1
        raise RuntimeError("full discovery should not run for explicit serial")


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

    def __init__(self, xml_text: str = XML_TEXT) -> None:
        self.calls: list[tuple[str, float]] = []
        self._xml_text = xml_text

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        self.calls.append((device_id, timeout_s))
        return DriverXmlDump.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            xml=self._xml_text,
            metadata={"displayWidth": "1080", "displayHeight": "2400"},
        )


class FakeScreenshotCapturer:
    backend_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []

    def capture(
        self,
        device_id: str,
        timeout_s: float = 10.0,
    ) -> DriverScreenshot:
        self.calls.append((device_id, timeout_s))
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
            },
        )


class FakeAppReader:
    backend_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []

    def app_current(
        self,
        device_id: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness:
        self.calls.append((device_id, timeout_s))
        return DriverAppAwareness.success(
            device_id=device_id,
            backend=self.backend_name,
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
        raise AssertionError("mobile snap must not call package_info")


def test_mobile_snap_default_table_has_targets_and_writes_latest_source(
    tmp_path: Path,
) -> None:
    app, xml_dumper, capturer, app_reader = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        cache_root=tmp_path / "latest",
    )
    result = CliRunner().invoke(app, ["snap", "RFCN4010FCK"])

    assert result.exit_code == 0
    latest = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path / "latest",
    )
    assert latest.device_id == "RFCN4010FCK"
    assert latest.session_id == "default"
    assert [target.display_id for target in latest.targets] == ["e001", "e002", "e003"]
    assert "RFCN4010FCK  com.example  1080x2400" in result.stdout
    assert "targets: 1 tap | 1 input | 1 scroll area | 3 visible" in result.stdout
    assert "scroll: 1 area detected; use --debug or --json for bounds" in result.stdout
    assert "e001" in result.stdout
    assert "input" in result.stdout
    assert "e002" in result.stdout
    assert "tap" in result.stdout
    assert "e003" not in result.stdout
    assert "scrollable" not in result.stdout
    assert XML_TEXT not in result.stdout
    assert "image_bytes" not in result.stdout
    assert xml_dumper.calls == [("RFCN4010FCK", 10.0)]
    assert capturer.calls == []
    assert app_reader.calls == [("RFCN4010FCK", 10.0)]


def test_mobile_snap_debug_table_includes_scroll_rows(tmp_path: Path) -> None:
    app, _xml_dumper, _capturer, _app_reader = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        cache_root=tmp_path / "latest",
    )

    result = CliRunner().invoke(
        app,
        ["snap", "RFCN4010FCK", "--debug"],
    )

    assert result.exit_code == 0
    assert "e003" in result.stdout
    assert "scroll" in result.stdout
    assert "scrollable" in result.stdout


def test_mobile_snap_default_table_marks_operator_label(tmp_path: Path) -> None:
    app, _xml_dumper, _capturer, _app_reader = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        cache_root=tmp_path / "latest",
        xml_text=XML_OPERATOR_LABEL_TEXT,
    )

    result = CliRunner().invoke(app, ["snap", "RFCN4010FCK"])

    assert result.exit_code == 0
    assert "Kontynuuj przy użyciu Instagramu~" in result.stdout
    assert "~ operator label; not target identity" in result.stdout
    latest = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path / "latest",
    )
    assert latest.targets[0].label is None


def test_mobile_snap_json_contract_and_debug_fields(tmp_path: Path) -> None:
    app, _xml_dumper, _capturer, _app_reader = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        cache_root=tmp_path / "latest",
    )

    result = CliRunner().invoke(
        app,
        ["snap", "RFCN4010FCK", "--json", "--debug"],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["schema_version"] == "mobile_snap.v1"
    assert payload["ok"] is True
    assert payload["snapshot"]["hash_version"] == "operator_observation_hash.v1"
    assert payload["summary"]["target_count"] == 3
    targets = payload["targets"]
    assert targets[0]["id"] == "e001"
    assert targets[0]["kind"] == "input"
    assert targets[0]["source_index"] == 0
    assert targets[0]["semantic_index"] == 0
    assert targets[0]["snapshot_id"] == payload["snapshot"]["snapshot_id"]
    assert targets[2]["kind"] == "scroll"
    assert targets[2]["scrollable"] is True
    assert "xml" not in payload
    assert XML_TEXT not in result.stdout
    assert "base64" not in result.stdout


def test_mobile_snap_explicit_serial_bypasses_full_discovery(tmp_path: Path) -> None:
    discovery = FailingDiscovery()
    app, xml_dumper, capturer, app_reader = _build_app(
        [],
        cache_root=tmp_path / "latest",
        discovery=discovery,
    )

    result = CliRunner().invoke(app, ["snap", "RFCN4010FCK", "--json"])

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["device_id"] == "RFCN4010FCK"
    assert discovery.calls == 0
    assert xml_dumper.calls == [("RFCN4010FCK", 10.0)]
    assert capturer.calls == []
    assert app_reader.calls == [("RFCN4010FCK", 10.0)]


def test_mobile_snap_requires_device_before_capture() -> None:
    app, xml_dumper, capturer, app_reader = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(app, ["snap", "--json"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "device_required"
    assert xml_dumper.calls == []
    assert capturer.calls == []
    assert app_reader.calls == []


def test_mobile_snap_rejects_positional_serial_with_device_option() -> None:
    app, xml_dumper, capturer, app_reader = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(
        app,
        ["snap", "RFCN4010FCK", "--device", "RFCN4010FCK", "--json"],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_arguments"
    assert xml_dumper.calls == []
    assert capturer.calls == []
    assert app_reader.calls == []


def _build_app(
    devices: Sequence[DeviceInfo],
    *,
    cache_root: Path | None = None,
    xml_text: str = XML_TEXT,
    discovery: FakeDiscovery | FailingDiscovery | None = None,
) -> tuple[typer.Typer, FakeXmlDumper, FakeScreenshotCapturer, FakeAppReader]:
    xml_dumper = FakeXmlDumper(xml_text)
    capturer = FakeScreenshotCapturer()
    app_reader = FakeAppReader()
    app = build_mobile_app(
        MobileDependencies(
            discovery=discovery or FakeDiscovery(devices),
            backend=FakeBackend(),
            lifecycle_runner=FakeLifecycleRunner(),
            xml_dumper=xml_dumper,
            screenshot_capturer=capturer,
            app_reader=app_reader,
            latest_cache_root=cache_root or Path("data/cache/mobile/latest-test"),
        )
    )
    return app, xml_dumper, capturer, app_reader


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
