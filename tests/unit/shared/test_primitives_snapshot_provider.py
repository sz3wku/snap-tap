from __future__ import annotations

from pathlib import Path

from snap_tap.backends.contracts import DriverScreenshot, DriverXmlDump
from snap_tap.device.identity import DeviceInfo
from snap_tap.primitives import (
    CorePrimitiveObservationProvider,
    CorePrimitiveSnapshotProvider,
)
from snap_tap.targets import build_snapshot_targets

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"
XML_TEXT = (
    '<hierarchy><node class="android.widget.Button" '
    'resource-id="com.example:id/safe" package="com.example" '
    'bounds="[10,20][110,220]" visible-to-user="true" '
    'enabled="true" clickable="true" content-desc="Safe" /></hierarchy>'
)


class FakeXmlDumper:
    backend_name = "fake"

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        return DriverXmlDump.success(
            device_id=device_id,
            backend="fake",
            elapsed_ms=1.0,
            xml=XML_TEXT,
        )


class FakeScreenshotCapturer:
    backend_name = "fake"

    def capture(self, device_id: str, timeout_s: float = 10.0) -> DriverScreenshot:
        return DriverScreenshot.success(
            device_id=device_id,
            backend="fake",
            elapsed_ms=1.0,
            image_bytes=PNG_BYTES,
            metadata={"format": "png", "width": 1080, "height": 2400},
        )


def test_core_primitive_snapshot_provider_materializes_resolution_refs(
    tmp_path: Path,
) -> None:
    provider = CorePrimitiveSnapshotProvider(
        devices=[DeviceInfo("RFCN4010FCK", "device")],
        xml_dumper=FakeXmlDumper(),
        screenshot_capturer=FakeScreenshotCapturer(),
        artifact_root=tmp_path,
    )

    result = provider.capture("RFCN4010FCK")

    assert result.ok is True
    assert result.snapshot is not None
    refs = result.snapshot.refs
    assert set(refs) == {"xml", "screenshot", "manifest"}
    assert all(ref.path for ref in refs.values())
    assert all(Path(ref.path).exists() for ref in refs.values())
    targets = build_snapshot_targets(result.snapshot)
    assert targets.targets[0].label == "Safe"


def test_core_primitive_observation_provider_uses_xml_without_artifact_refs() -> None:
    provider = CorePrimitiveObservationProvider(
        devices=[DeviceInfo("RFCN4010FCK", "device")],
        xml_dumper=FakeXmlDumper(),
    )

    result = provider.capture("RFCN4010FCK")

    assert result.ok is True
    assert result.snapshot is not None
    assert result.snapshot.refs == {}
    targets = build_snapshot_targets(result.snapshot)
    assert targets.targets[0].label == "Safe"
    assert result.snapshot.screen_metadata.viewport.width == 110
    assert result.snapshot.screen_metadata.viewport.height == 220
