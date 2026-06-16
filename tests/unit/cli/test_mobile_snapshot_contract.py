from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any, cast

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
    'enabled="true" clickable="true" text="Secret raw text" '
    'content-desc="Public label" hint="Raw hint" /></hierarchy>'
)

SEMANTIC_TOP_LEVEL_KEYS = {
    "schema_version",
    "snapshot_id",
    "device_id",
    "captured_at",
    "refs",
    "elements",
    "screen_metadata",
    "role_normalization",
}

RAW_ELEMENT_PRIVATE_KEYS = {"text", "content-desc", "content_desc", "hint"}
FORBIDDEN_PUBLIC_STRINGS = (
    XML_TEXT,
    "image_bytes",
    "image_base64",
    "base64",
    "target_id",
    "target_signature",
    "primitive_receipt",
    "latest_snapshot",
    "screen_id",
    "screen_hint",
    "safe_next_actions",
    "model_prompt",
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

    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        self.calls.append((device_id, timeout_s))
        return DriverXmlDump.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            xml=XML_TEXT,
            metadata={"timeout_s": timeout_s},
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
                "sha256": "abc123",
                "timeout_s": timeout_s,
            },
        )


def test_mobile_snapshot_semantics_contract_shape_is_scriptable(
    tmp_path: Path,
) -> None:
    app, xml_dumper, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(
        app,
        [
            "snapshot",
            "--device",
            "RFCN4010FCK",
            "--out-dir",
            str(tmp_path),
            "--timeout-s",
            "3",
        ],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    semantic = cast(dict[str, object], payload["result"]["semantics"])
    assert set(semantic) == SEMANTIC_TOP_LEVEL_KEYS
    assert semantic["schema_version"] == "semantic_snapshot.v1"
    assert semantic["device_id"] == "RFCN4010FCK"
    assert isinstance(semantic["snapshot_id"], str)
    assert isinstance(semantic["captured_at"], str)

    refs = cast(dict[str, dict[str, object]], semantic["refs"])
    assert set(refs) == {"xml", "screenshot", "manifest"}
    assert refs["xml"]["node_count"] == 1
    assert refs["screenshot"]["format"] == "png"
    assert refs["screenshot"]["width"] == 1080
    assert refs["screenshot"]["height"] == 2400
    assert refs["manifest"]["metadata"] == {
        "schema_version": "snapshot_manifest.v1"
    }

    elements = cast(list[dict[str, object]], semantic["elements"])
    assert len(elements) == 1
    assert elements[0]["source_index"] == 0
    assert elements[0]["role"] == "button"
    assert elements[0]["label"] == "Public label"
    assert elements[0]["label_source"] == "content_desc"
    assert elements[0]["accessibility"] == {
        "text": "Secret raw text",
        "content_desc": "Public label",
        "hint": "Raw hint",
    }
    assert semantic["screen_metadata"] == {
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

    json.dumps(payload, sort_keys=True)
    for forbidden in FORBIDDEN_PUBLIC_STRINGS:
        assert forbidden not in result.stdout
    assert xml_dumper.calls == [("RFCN4010FCK", 3.0)]
    assert capturer.calls == [("RFCN4010FCK", 3.0)]


def test_mobile_snapshot_raw_elements_keep_private_text_out(
    tmp_path: Path,
) -> None:
    app, _xml_dumper, _capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(
        app,
        ["snapshot", "--device", "RFCN4010FCK", "--out-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    raw_elements = cast(list[dict[str, object]], payload["result"]["elements"])
    assert len(raw_elements) == 1
    assert RAW_ELEMENT_PRIVATE_KEYS.isdisjoint(raw_elements[0])


def test_mobile_snapshot_failure_before_capture_has_no_partial_semantics_or_refs(
    tmp_path: Path,
) -> None:
    app, xml_dumper, capturer = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(app, ["snapshot", "--out-dir", str(tmp_path)])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["semantics"] is None
    assert payload["result"]["refs"] == {}
    assert payload["result"]["elements"] == []
    assert payload["result"]["normalization"] is None
    assert xml_dumper.calls == []
    assert capturer.calls == []
    assert list(tmp_path.iterdir()) == []


def _build_app(
    devices: Sequence[DeviceInfo],
) -> tuple[typer.Typer, FakeXmlDumper, FakeScreenshotCapturer]:
    fake_xml_dumper = FakeXmlDumper()
    fake_capturer = FakeScreenshotCapturer()
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
