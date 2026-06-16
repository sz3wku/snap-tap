from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import typer
from typer.testing import CliRunner

import snap_tap.snapshots.artifacts as artifacts_module
from snap_tap.backends.contracts import (
    DriverHealth,
    DriverLifecycleResult,
    DriverScreenshot,
    DriverXmlDump,
)
from snap_tap.cli.mobile.app import MobileDependencies, build_mobile_app
from snap_tap.device.identity import DeviceInfo

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"
XML_TEXT = (
    '<hierarchy><node bounds="[10,20][110,220]" visible-to-user="true" '
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
            xml=XML_TEXT,
            metadata={"timeout_s": str(timeout_s)},
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


def test_mobile_snapshot_reuses_out_dir_with_unique_capture_dirs(
    tmp_path: Path,
) -> None:
    app = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])
    runner = CliRunner()
    out_dir = tmp_path / "snapshot"

    first = runner.invoke(
        app,
        ["snapshot", "--device", "RFCN4010FCK", "--out-dir", str(out_dir)],
    )
    second = runner.invoke(
        app,
        ["snapshot", "--device", "RFCN4010FCK", "--out-dir", str(out_dir)],
    )

    assert first.exit_code == 0
    assert second.exit_code == 0
    first_payload = _json(first.stdout)
    second_payload = _json(second.stdout)
    first_manifest_ref = first_payload["result"]["refs"]["manifest"]
    second_manifest_ref = second_payload["result"]["refs"]["manifest"]
    first_dir = Path(str(first_manifest_ref["path"]))
    second_dir = Path(str(second_manifest_ref["path"]))
    assert first_dir.parent != second_dir.parent
    assert first_dir.parent.parent == out_dir
    assert second_dir.parent.parent == out_dir
    assert sorted(path.name for path in first_dir.parent.iterdir()) == [
        "manifest.json",
        "screen.png",
        "screen.xml",
    ]
    assert sorted(path.name for path in second_dir.parent.iterdir()) == [
        "manifest.json",
        "screen.png",
        "screen.xml",
    ]
    manifest_bytes = first_dir.read_bytes()
    manifest = json.loads(manifest_bytes)
    assert first_manifest_ref["sha256"] == hashlib.sha256(manifest_bytes).hexdigest()
    assert first_manifest_ref["byte_length"] == len(manifest_bytes)
    assert first_manifest_ref["metadata"] == {
        "schema_version": "snapshot_manifest.v1"
    }
    assert manifest["schema_version"] == "snapshot_manifest.v1"
    assert manifest["snapshot"]["snapshot_id"] == first_payload["result"][
        "snapshot_id"
    ]
    assert manifest["snapshot"]["snapshot_hash"] == first_payload["result"][
        "snapshot_hash"
    ]
    assert manifest["artifacts"]["xml"]["path"] == "screen.xml"
    assert manifest["artifacts"]["screenshot"]["path"] == "screen.png"


def test_mobile_snapshot_cleans_capture_dir_when_manifest_write_fails(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    def fail_manifest(path: Path, payload: bytes) -> None:
        if path.name == "manifest.json":
            raise OSError("manifest blocked")
        path.write_bytes(payload)

    monkeypatch.setattr(artifacts_module, "_write_bytes_atomically", fail_manifest)
    app = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(
        app,
        ["snapshot", "--device", "RFCN4010FCK", "--out-dir", str(tmp_path)],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["result"]["error"]["code"] == "snapshot_evidence_missing"
    assert payload["result"]["refs"] == {}
    assert list(tmp_path.iterdir()) == []


def _build_app(devices: Sequence[DeviceInfo]) -> typer.Typer:
    return build_mobile_app(
        MobileDependencies(
            discovery=FakeDiscovery(devices),
            backend=FakeBackend(),
            lifecycle_runner=FakeLifecycleRunner(),
            xml_dumper=FakeXmlDumper(),
            screenshot_capturer=FakeScreenshotCapturer(),
        )
    )


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
