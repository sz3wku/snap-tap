from __future__ import annotations

import base64
from collections.abc import Sequence

from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessResult,
    ProcessRunner,
    ProcessTimeoutError,
)
from snap_tap.backends.android.uiautomator2.screenshot import capture_uiautomator2_screenshot


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"


class FakeProcessRunner(ProcessRunner):
    def __init__(
        self,
        result: ProcessResult | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.calls: list[tuple[list[str], float]] = []
        self._result = result or ProcessResult(returncode=0, stdout="", stderr="")
        self._exc = exc

    def run(self, args: Sequence[str], timeout_s: float) -> ProcessResult:
        self.calls.append((list(args), timeout_s))
        if self._exc is not None:
            raise self._exc
        return self._result


def test_capture_uiautomator2_screenshot_rejects_malformed_serial_without_subprocess() -> None:
    runner = FakeProcessRunner()

    result = capture_uiautomator2_screenshot(
        device_id="bad serial",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.status == "blocked"
    assert result.error is not None
    assert result.error.code == "device_offline"
    assert runner.calls == []


def test_capture_uiautomator2_screenshot_runs_probe_as_argument_list() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=0,
            stdout=_probe_success(PNG_BYTES),
            stderr="",
        )
    )

    result = capture_uiautomator2_screenshot(
        device_id="RFCN4010FCK",
        timeout_s=3.0,
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is True
    assert result.image_bytes == PNG_BYTES
    assert result.metadata["format"] == "png"
    assert result.metadata["width"] == 1080
    assert result.metadata["height"] == 2400
    assert result.metadata["byte_length"] == len(PNG_BYTES)
    assert isinstance(result.metadata["sha256"], str)
    assert result.metadata["timeout_s"] == 3.0
    assert runner.calls == [
        (
            [
                ".venv",
                "-m",
                "snap_tap.backends.android.uiautomator2.probes",
                "screenshot",
                "--device",
                "RFCN4010FCK",
            ],
            3.0,
        )
    ]


def test_capture_uiautomator2_screenshot_timeout_returns_structured_failure() -> None:
    runner = FakeProcessRunner(exc=ProcessTimeoutError("screenshot timed out"))

    result = capture_uiautomator2_screenshot(
        device_id="RFCN4010FCK",
        timeout_s=0.01,
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_timeout"
    assert result.metadata["timeout_s"] == 0.01


def test_capture_uiautomator2_screenshot_process_error_is_structured() -> None:
    runner = FakeProcessRunner(exc=OSError("python missing"))

    result = capture_uiautomator2_screenshot(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_unavailable"
    assert "python missing" in result.error.detail


def test_capture_uiautomator2_screenshot_failed_probe_is_structured() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=1,
            stdout=(
                '{"ok": false, "error": {"code": "screenshot_failed", '
                '"detail": "RuntimeError: blocked"}}'
            ),
            stderr="",
        )
    )

    result = capture_uiautomator2_screenshot(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "screenshot_failed"
    assert "blocked" in result.error.detail


def test_capture_uiautomator2_screenshot_does_not_echo_malformed_stdout() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=1,
            stdout='{"ok": false, "image_base64": "secret-screenshot-bytes"',
            stderr="",
        )
    )

    result = capture_uiautomator2_screenshot(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "screenshot_failed"
    assert "image_base64" not in result.error.detail
    assert "secret-screenshot-bytes" not in result.error.detail


def test_capture_uiautomator2_screenshot_redacts_sensitive_structured_error() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=1,
            stdout=(
                '{"ok": false, "error": {"code": "screenshot_failed", '
                '"detail": "image_base64=secret-screenshot-bytes"}}'
            ),
            stderr="",
        )
    )

    result = capture_uiautomator2_screenshot(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "screenshot_failed"
    assert "image_base64" not in result.error.detail
    assert "secret-screenshot-bytes" not in result.error.detail


def test_capture_uiautomator2_screenshot_omits_hostile_probe_metadata() -> None:
    encoded = base64.b64encode(b"not-png").decode("ascii")
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=0,
            stdout=(
                '{"ok": true, '
                f'"image_base64": "{encoded}", '
                '"metadata": {'
                '"format": "png", '
                '"width": 1, '
                '"height": 1, '
                '"image_base64": "secret-metadata", '
                '"path": "private-path"'
                "}}"
            ),
            stderr="",
        )
    )

    result = capture_uiautomator2_screenshot(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "screenshot_failed"
    assert result.metadata == {
        "timeout_s": 10.0,
        "format": "png",
        "width": 1,
        "height": 1,
    }


def test_capture_uiautomator2_screenshot_rejects_empty_payload() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(returncode=0, stdout='{"ok": true}', stderr="")
    )

    result = capture_uiautomator2_screenshot(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "screenshot_failed"


def test_capture_uiautomator2_screenshot_rejects_invalid_base64() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=0,
            stdout=(
                '{"ok": true, "image_base64": "@@@", '
                '"metadata": {"format": "png", "width": 1, "height": 1}}'
            ),
            stderr="",
        )
    )

    result = capture_uiautomator2_screenshot(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "screenshot_failed"


def test_capture_uiautomator2_screenshot_rejects_non_png_payload() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=0,
            stdout=_probe_success(b"not-png"),
            stderr="",
        )
    )

    result = capture_uiautomator2_screenshot(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "screenshot_failed"


def _probe_success(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return (
        '{"ok": true, '
        f'"image_base64": "{encoded}", '
        '"metadata": {"format": "png", "width": 1080, "height": 2400}}'
    )
