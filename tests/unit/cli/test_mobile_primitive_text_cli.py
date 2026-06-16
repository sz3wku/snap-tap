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
from snap_tap.backends.contracts import DriverText
from snap_tap.backends.android.uiautomator2.text import TEXT_INPUT_MODE, TEXT_REPLACE_MODE
from snap_tap.backends.contracts import DriverXmlDump
from snap_tap.primitives import (
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
    PrimitiveTextRequest,
    resolved_text,
)
from snap_tap.primitives.receipt import utc_now
from snap_tap.semantics import (
    SEMANTIC_SCREEN_METADATA_SCHEMA_VERSION,
    SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
    SemanticElement,
    SemanticRole,
    SemanticScreenCounts,
    SemanticScreenMetadata,
    SemanticSnapshot,
    SemanticViewport,
    ViewportOrientation,
)
from snap_tap.snapshots import SnapshotArtifactRef, SnapshotBounds
from snap_tap.targets import build_snapshot_targets, build_target_signature
from snap_tap.targets.signature import target_signature_to_dict


class FakeDiscovery:
    def __init__(self, devices: Sequence[DeviceInfo]) -> None:
        self._devices = tuple(devices)

    def list_devices(self) -> Sequence[DeviceInfo]:
        return self._devices


class FakeBackend:
    backend_name = "fake"

    def health(self, device_id: str, timeout_s: float = 5.0) -> DriverHealth:
        return DriverHealth.success(
            device_id=device_id,
            backend="fake",
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
            backend="fake",
            operation=operation,
            elapsed_ms=1.0,
        )


class FakeXmlDumper:
    backend_name = "fake"

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        raise AssertionError("primitive CLI unit tests must not dump XML")


class FakeScreenshotCapturer:
    backend_name = "fake"

    def capture(self, device_id: str, timeout_s: float = 10.0) -> DriverScreenshot:
        raise AssertionError("primitive CLI unit tests must not capture screenshots")


class FakeTextExecutor:
    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.calls: list[PrimitiveTextRequest] = []

    def input_text(self, request: PrimitiveTextRequest) -> PrimitiveReceipt:
        self.calls.append(request)
        snapshot_id = "fresh" if self.mode == "success" else "source"
        provider = _Provider(
            [_snapshot_result(snapshot_id), _snapshot_result("after")]
            if self.mode == "success"
            else [_snapshot_result(snapshot_id)]
        )
        return resolved_text(
            request,
            snapshot_provider=provider,
            texter=_Texter(_driver_result(request.mode)),
        )


class _Provider:
    def __init__(self, results: list[PrimitiveSnapshotResult]) -> None:
        self.results = results

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        return self.results.pop(0)


class _Texter:
    backend_name = "fake"

    def __init__(self, result: DriverText) -> None:
        self.result = result

    def input_text(
        self,
        *,
        device_id: str,
        x: float,
        y: float,
        text: str,
        mode: str,
        timeout_s: float = 10.0,
    ) -> DriverText:
        return self.result


def test_primitive_input_success_outputs_receipt_json(tmp_path: Path) -> None:
    signature_file = _write_signature(tmp_path)
    executor = FakeTextExecutor()
    app = _build_app(executor)

    result = CliRunner().invoke(
        app,
        [
            "primitive-input",
            "--device",
            "RFCN4010FCK",
            "--signature-file",
            str(signature_file),
            "--text",
            "hakar smoke",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["schema_version"] == "primitive_receipt.v1"
    assert payload["operation"] == "input"
    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert payload["attempted_touch"] is True
    assert payload["touched_phone"] is True
    assert "hakar smoke" not in result.stdout
    assert payload["request"]["text_length"] == 11
    assert len(executor.calls) == 1
    assert executor.calls[0].text == "hakar smoke"


def test_primitive_replace_text_success_outputs_replace_receipt(
    tmp_path: Path,
) -> None:
    signature_file = _write_signature(tmp_path)
    executor = FakeTextExecutor()
    app = _build_app(executor)

    result = CliRunner().invoke(
        app,
        [
            "primitive-replace-text",
            "--device",
            "RFCN4010FCK",
            "--signature-file",
            str(signature_file),
            "--text",
            "new text",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["operation"] == "replace_text"
    assert "new text" not in result.stdout
    assert executor.calls[0].mode == TEXT_REPLACE_MODE
    assert executor.calls[0].text == "new text"


def test_primitive_input_missing_text_fails_before_executor(tmp_path: Path) -> None:
    signature_file = _write_signature(tmp_path)
    executor = FakeTextExecutor()
    app = _build_app(executor)

    result = CliRunner().invoke(
        app,
        [
            "primitive-input",
            "--device",
            "RFCN4010FCK",
            "--signature-file",
            str(signature_file),
            "--json",
        ],
    )

    assert result.exit_code != 0
    assert executor.calls == []


def test_primitive_input_empty_text_fails_before_executor(tmp_path: Path) -> None:
    signature_file = _write_signature(tmp_path)
    executor = FakeTextExecutor()
    app = _build_app(executor)

    result = CliRunner().invoke(
        app,
        [
            "primitive-input",
            "--device",
            "RFCN4010FCK",
            "--signature-file",
            str(signature_file),
            "--text",
            "",
            "--json",
        ],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["error"]["code"] == "primitive_invalid_request"
    assert "hello" not in result.stdout
    assert executor.calls == []


def test_primitive_input_bad_serial_fails_before_executor(tmp_path: Path) -> None:
    signature_file = _write_signature(tmp_path)
    executor = FakeTextExecutor()
    app = _build_app(executor)

    result = CliRunner().invoke(
        app,
        [
            "primitive-input",
            "--device",
            "bad serial",
            "--signature-file",
            str(signature_file),
            "--text",
            "hello",
            "--json",
        ],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["error"]["code"] == "primitive_invalid_request"
    assert executor.calls == []


def test_primitive_input_missing_signature_fails_before_executor(
    tmp_path: Path,
) -> None:
    executor = FakeTextExecutor()
    app = _build_app(executor)

    result = CliRunner().invoke(
        app,
        [
            "primitive-input",
            "--device",
            "RFCN4010FCK",
            "--signature-file",
            str(tmp_path / "missing.json"),
            "--text",
            "hello",
            "--json",
        ],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["error"]["code"] == "primitive_invalid_request"
    assert executor.calls == []


def test_primitive_input_resolution_blocked_returns_receipt(tmp_path: Path) -> None:
    signature_file = _write_signature(tmp_path)
    app = _build_app(FakeTextExecutor("blocked"))

    result = CliRunner().invoke(
        app,
        [
            "primitive-input",
            "--device",
            "RFCN4010FCK",
            "--signature-file",
            str(signature_file),
            "--text",
            "hello",
            "--json",
        ],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["schema_version"] == "primitive_receipt.v1"
    assert payload["status"] == "blocked"
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False


def _build_app(executor: FakeTextExecutor) -> typer.Typer:
    return build_mobile_app(
        MobileDependencies(
            discovery=FakeDiscovery([DeviceInfo("RFCN4010FCK", "device")]),
            backend=FakeBackend(),
            lifecycle_runner=FakeLifecycleRunner(),
            xml_dumper=FakeXmlDumper(),
            screenshot_capturer=FakeScreenshotCapturer(),
            primitive_text_executor=executor,
        )
    )


def _write_signature(tmp_path: Path) -> Path:
    path = tmp_path / "target_signature.json"
    source = build_snapshot_targets(_snapshot("source"))
    signature = build_target_signature(source, "e001")
    path.write_text(json.dumps(target_signature_to_dict(signature)), encoding="utf-8")
    return path


def _snapshot_result(snapshot_id: str) -> PrimitiveSnapshotResult:
    snapshot = _snapshot(snapshot_id)
    return PrimitiveSnapshotResult(
        ok=True,
        status="completed",
        device_id=snapshot.device_id,
        checked_at=snapshot.captured_at,
        elapsed_ms=1.0,
        snapshot=snapshot,
    )


def _snapshot(snapshot_id: str) -> SemanticSnapshot:
    element = SemanticElement(
        source_index=7,
        role=SemanticRole.INPUT,
        bounds=SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
        enabled=True,
        clickable=True,
        scrollable=False,
        label="Message",
        label_source="hint",
        class_name="android.widget.EditText",
        resource_id="com.example:id/message",
        package="com.example",
    )
    return SemanticSnapshot(
        schema_version=SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        device_id="RFCN4010FCK",
        captured_at="2026-06-14T10:00:00+00:00",
        refs={
            "xml": SnapshotArtifactRef(
                path="screen.xml",
                sha256="xml-sha",
                byte_length=123,
            )
        },
        elements=(element,),
        screen_metadata=SemanticScreenMetadata(
            schema_version=SEMANTIC_SCREEN_METADATA_SCHEMA_VERSION,
            viewport=SemanticViewport(
                orientation=ViewportOrientation.PORTRAIT,
                width=1080,
                height=2400,
            ),
            counts=SemanticScreenCounts(
                source_element_count=1,
                visible_element_count=1,
                semantic_element_count=1,
                enabled_count=1,
                clickable_count=1,
                actionable_count=1,
                labeled_count=1,
                unknown_count=0,
            ),
        ),
    )


def _driver_result(operation: str = TEXT_INPUT_MODE) -> DriverText:
    return DriverText(
        ok=True,
        status="completed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation=operation,
        elapsed_ms=1.0,
        attempted=True,
        confirmed=True,
        checked_at=utc_now(),
    )


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
