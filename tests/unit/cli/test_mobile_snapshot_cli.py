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
XML_TEXT = (
    '<hierarchy><node class="android.widget.Button" '
    'resource-id="com.example:id/ok" package="com.example" '
    'bounds="[10,20][110,220]" visible-to-user="true" '
    'enabled="true" clickable="true" text="secret" '
    'content-desc="redacted" /></hierarchy>'
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
            metadata={"timeout_s": str(timeout_s)},
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
                "byte_length": len(PNG_BYTES),
                "sha256": "abc123",
                "timeout_s": timeout_s,
            },
        )


def test_mobile_snapshot_requires_device(tmp_path: Path) -> None:
    app, xml_dumper, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(app, ["snapshot", "--out-dir", str(tmp_path)])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "device_required"
    assert xml_dumper.calls == []
    assert capturer.calls == []


def test_mobile_snapshot_requires_out_dir() -> None:
    app, xml_dumper, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(app, ["snapshot", "--device", "RFCN4010FCK"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "invalid_arguments"
    assert xml_dumper.calls == []
    assert capturer.calls == []


def test_mobile_snapshot_rejects_malformed_serial_before_capture(
    tmp_path: Path,
) -> None:
    app, xml_dumper, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(
        app,
        ["snapshot", "--device", "bad serial", "--out-dir", str(tmp_path)],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "device_offline"
    assert xml_dumper.calls == []
    assert capturer.calls == []
    assert not (tmp_path / "screen.xml").exists()
    assert not (tmp_path / "screen.png").exists()


def test_mobile_snapshot_writes_refs_and_omits_raw_payloads(tmp_path: Path) -> None:
    app, xml_dumper, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )
    out_dir = tmp_path / "snapshot"

    result = CliRunner().invoke(
        app,
        [
            "snapshot",
            "RFCN4010FCK",
            "--out-dir",
            str(out_dir),
            "--timeout-s",
            "3",
        ],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    xml_path = Path(str(payload["result"]["refs"]["xml"]["path"]))
    screenshot_path = Path(str(payload["result"]["refs"]["screenshot"]["path"]))
    assert xml_path.read_text(encoding="utf-8") == XML_TEXT
    assert screenshot_path.read_bytes() == PNG_BYTES
    assert xml_path.parent == screenshot_path.parent
    assert xml_path.parent.parent == out_dir
    assert xml_path.parent.name.startswith("capture-")
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "snapshot_capture"
    assert str(payload["result"]["snapshot_id"]).startswith("snap_")
    assert str(payload["result"]["snapshot_hash"]).startswith("sha256:")
    assert payload["result"]["hash_version"] == "raw_snapshot_hash.v1"
    assert payload["result"]["refs"]["xml"]["path"] == str(xml_path)
    assert payload["result"]["refs"]["xml"]["byte_length"] == len(
        XML_TEXT.encode("utf-8")
    )
    assert payload["result"]["refs"]["xml"]["node_count"] == 1
    assert payload["result"]["refs"]["screenshot"]["path"] == str(screenshot_path)
    assert payload["result"]["refs"]["screenshot"]["format"] == "png"
    assert payload["result"]["refs"]["screenshot"]["width"] == 1080
    assert payload["result"]["refs"]["screenshot"]["height"] == 2400
    assert payload["result"]["normalization"]["schema_version"] == (
        "snapshot_elements.v1"
    )
    assert payload["result"]["normalization"]["source_node_count"] == 1
    assert payload["result"]["normalization"]["element_count"] == 1
    assert payload["result"]["normalization"]["visible_count"] == 1
    assert payload["result"]["normalization"]["enabled_count"] == 1
    assert payload["result"]["normalization"]["clickable_count"] == 1
    assert payload["result"]["normalization"]["scrollable_count"] == 0
    assert payload["result"]["normalization"]["viewport_width"] == 1080
    assert payload["result"]["normalization"]["viewport_height"] == 2400
    assert payload["result"]["elements"] == [
        {
            "source_index": 0,
            "depth": 0,
            "bounds": {
                "left": 10,
                "top": 20,
                "right": 110,
                "bottom": 220,
                "width": 100,
                "height": 200,
                "center_x": 60.0,
                "center_y": 120.0,
            },
            "visible": True,
            "enabled": True,
            "clickable": True,
            "scrollable": False,
            "class_name": "android.widget.Button",
            "resource_id": "com.example:id/ok",
            "package": "com.example",
        }
    ]
    assert payload["result"]["semantics"]["schema_version"] == "semantic_snapshot.v1"
    assert payload["result"]["semantics"]["elements"] == [
        {
            "source_index": 0,
            "role": "button",
            "bounds": {
                "left": 10,
                "top": 20,
                "right": 110,
                "bottom": 220,
                "width": 100,
                "height": 200,
                "center_x": 60.0,
                "center_y": 120.0,
            },
            "enabled": True,
            "clickable": True,
            "scrollable": False,
            "label": "redacted",
            "label_source": "content_desc",
            "accessibility": {
                "text": "secret",
                "content_desc": "redacted",
            },
            "class_name": "android.widget.Button",
            "resource_id": "com.example:id/ok",
            "package": "com.example",
        }
    ]
    assert payload["result"]["semantics"]["screen_metadata"] == {
        "schema_version": "semantic_screen_metadata.v1",
        "viewport": {
            "width": 1080,
            "height": 2400,
            "orientation": "portrait",
        },
        "packages": [
            {
                "package": "com.example",
                "element_count": 1,
                "visible_count": 1,
                "semantic_count": 1,
            }
        ],
        "dominant_package": "com.example",
        "counts": {
            "source_element_count": 1,
            "visible_element_count": 1,
            "semantic_element_count": 1,
            "enabled_count": 1,
            "clickable_count": 1,
            "scrollable_count": 0,
            "actionable_count": 1,
            "labeled_count": 1,
            "unknown_count": 0,
        },
    }
    assert "text" not in payload["result"]["elements"][0]
    assert "content_desc" not in payload["result"]["elements"][0]
    assert "content-desc" not in payload["result"]["elements"][0]
    assert "hint" not in payload["result"]["elements"][0]
    assert "xml" not in payload["result"]
    assert "image_base64" not in result.stdout
    assert "image_bytes" not in result.stdout
    assert XML_TEXT not in result.stdout
    assert xml_dumper.calls == [("RFCN4010FCK", 3.0)]
    assert capturer.calls == [("RFCN4010FCK", 3.0)]


def test_mobile_snapshot_rejects_positional_serial_with_device_option(
    tmp_path: Path,
) -> None:
    app, xml_dumper, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(
        app,
        [
            "snapshot",
            "RFCN4010FCK",
            "--device",
            "RFCN4010FCK",
            "--out-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "invalid_arguments"
    assert xml_dumper.calls == []
    assert capturer.calls == []


def test_mobile_snapshot_exposes_recovery_metadata(tmp_path: Path) -> None:
    recovered_xml = DriverXmlDump.success(
        device_id="RFCN4010FCK",
        backend="fake",
        elapsed_ms=1.0,
        xml=XML_TEXT,
        metadata={
            "recovery_attempted": True,
            "recovery_ok": True,
            "recovery_operation": "init",
            "recovered_after_failure": "driver_unavailable",
            "recovery_elapsed_ms": 12.0,
            "attempt": 2,
        },
    )
    app, _xml_dumper, _capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        xml_dumper=FakeXmlDumper(recovered_xml),
    )

    result = CliRunner().invoke(
        app,
        ["snapshot", "--device", "RFCN4010FCK", "--out-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["result"]["recovery"]["xml"]["recovery_attempted"] is True
    assert payload["result"]["recovery"]["xml"]["recovery_ok"] is True
    assert payload["result"]["recovery"]["xml"]["recovery_operation"] == "init"


def test_mobile_snapshot_redacts_hostile_failure_detail(tmp_path: Path) -> None:
    hostile_xml = DriverXmlDump.failure(
        backend="fake",
        code="dump_failed",
        detail="<hierarchy><node text='secret' /></hierarchy>",
        device_id="RFCN4010FCK",
        elapsed_ms=1.0,
    )
    app, _xml_dumper, _capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        xml_dumper=FakeXmlDumper(hostile_xml),
    )

    result = CliRunner().invoke(
        app,
        ["snapshot", "--device", "RFCN4010FCK", "--out-dir", str(tmp_path)],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["result"]["error"]["detail"] == "Snapshot XML capture failed."
    assert "<hierarchy" not in result.stdout
    assert "secret" not in result.stdout


def test_mobile_snapshot_does_not_write_when_xml_capture_fails(tmp_path: Path) -> None:
    xml_failure = DriverXmlDump.failure(
        backend="fake",
        code="dump_failed",
        detail="blocked",
        device_id="RFCN4010FCK",
        elapsed_ms=1.0,
    )
    app, _xml_dumper, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        xml_dumper=FakeXmlDumper(xml_failure),
    )

    result = CliRunner().invoke(
        app,
        ["snapshot", "--device", "RFCN4010FCK", "--out-dir", str(tmp_path)],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["result"]["error"]["code"] == "snapshot_dump_failed"
    assert payload["result"]["semantics"] is None
    assert capturer.calls == []
    assert not (tmp_path / "screen.xml").exists()
    assert not (tmp_path / "screen.png").exists()


def test_mobile_snapshot_does_not_write_when_screenshot_fails(
    tmp_path: Path,
) -> None:
    screenshot_failure = DriverScreenshot.failure(
        backend="fake",
        code="screenshot_failed",
        detail="blocked",
        device_id="RFCN4010FCK",
        elapsed_ms=1.0,
    )
    app, _xml_dumper, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        capturer=FakeScreenshotCapturer(screenshot_failure),
    )

    result = CliRunner().invoke(
        app,
        ["snapshot", "--device", "RFCN4010FCK", "--out-dir", str(tmp_path)],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["result"]["error"]["code"] == "snapshot_evidence_missing"
    assert capturer.calls == [("RFCN4010FCK", 10.0)]
    assert not (tmp_path / "screen.xml").exists()
    assert not (tmp_path / "screen.png").exists()


def _build_app(
    devices: Sequence[DeviceInfo],
    *,
    xml_dumper: FakeXmlDumper | None = None,
    capturer: FakeScreenshotCapturer | None = None,
) -> tuple[typer.Typer, FakeXmlDumper, FakeScreenshotCapturer]:
    fake_xml_dumper = xml_dumper or FakeXmlDumper()
    fake_capturer = capturer or FakeScreenshotCapturer()
    app = build_mobile_app(
        MobileDependencies(
            discovery=FakeDiscovery(devices),
            backend=FakeBackend(),
            lifecycle_runner=FakeLifecycleRunner(),
            xml_dumper=fake_xml_dumper,
            screenshot_capturer=fake_capturer,
        )
    )
    return app, fake_xml_dumper, fake_capturer


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
