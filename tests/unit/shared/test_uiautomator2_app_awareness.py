from __future__ import annotations

from collections.abc import Sequence

from snap_tap.backends.android.uiautomator2.app_awareness import (
    read_uiautomator2_app_current,
    read_uiautomator2_package_info,
)
from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessResult,
    ProcessRunner,
    ProcessTimeoutError,
)


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


def test_uiautomator2_app_current_rejects_malformed_serial_without_subprocess() -> None:
    runner = FakeProcessRunner()

    result = read_uiautomator2_app_current(
        device_id="bad serial",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.status == "blocked"
    assert result.error is not None
    assert result.error.code == "device_offline"
    assert runner.calls == []


def test_uiautomator2_app_current_runs_probe_as_argument_list() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=0,
            stdout=(
                '{"ok": true, "metadata": {'
                '"package": "com.example.app", '
                '"activity": ".MainActivity", '
                '"pid": 123, '
                '"raw": "not-public"}}'
            ),
            stderr="",
        )
    )

    result = read_uiautomator2_app_current(
        device_id="RFCN4010FCK",
        timeout_s=3.0,
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is True
    assert result.metadata["package"] == "com.example.app"
    assert result.metadata["activity"] == ".MainActivity"
    assert result.metadata["pid"] == 123
    assert "raw" not in result.metadata
    assert runner.calls == [
        (
            [
                ".venv",
                "-m",
                "snap_tap.backends.android.uiautomator2.probes",
                "app_current",
                "--device",
                "RFCN4010FCK",
            ],
            3.0,
        )
    ]


def test_uiautomator2_package_info_normalizes_package_before_subprocess() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=0,
            stdout=(
                '{"ok": true, "metadata": {'
                '"package": "com.example.app", '
                '"version_name": "1.2.3", '
                '"version_code": "42", '
                '"private": "ignored"}}'
            ),
            stderr="",
        )
    )

    result = read_uiautomator2_package_info(
        device_id="RFCN4010FCK",
        package=" com.example.app ",
        timeout_s=4.0,
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is True
    assert result.metadata["package"] == "com.example.app"
    assert result.metadata["version_name"] == "1.2.3"
    assert result.metadata["version_code"] == 42
    assert "private" not in result.metadata
    assert runner.calls == [
        (
            [
                ".venv",
                "-m",
                "snap_tap.backends.android.uiautomator2.probes",
                "package_info",
                "--device",
                "RFCN4010FCK",
                "--package",
                "com.example.app",
            ],
            4.0,
        )
    ]


def test_uiautomator2_package_info_uses_requested_package_when_probe_omits_it() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=0,
            stdout=(
                '{"ok": true, "metadata": {'
                '"version_name": "1.2.3", '
                '"version_code": "42"}}'
            ),
            stderr="",
        )
    )

    result = read_uiautomator2_package_info(
        device_id="RFCN4010FCK",
        package="com.example.app",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is True
    assert result.metadata["package"] == "com.example.app"
    assert result.metadata["version_name"] == "1.2.3"
    assert result.metadata["version_code"] == 42


def test_uiautomator2_package_info_rejects_malformed_package_without_subprocess() -> None:
    runner = FakeProcessRunner()

    result = read_uiautomator2_package_info(
        device_id="RFCN4010FCK",
        package="bad package",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.status == "blocked"
    assert result.error is not None
    assert result.error.code == "app_unavailable"
    assert runner.calls == []


def test_uiautomator2_app_current_timeout_returns_structured_failure() -> None:
    runner = FakeProcessRunner(exc=ProcessTimeoutError("app timed out"))

    result = read_uiautomator2_app_current(
        device_id="RFCN4010FCK",
        timeout_s=0.01,
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_timeout"
    assert result.metadata["timeout_s"] == 0.01


def test_uiautomator2_app_current_process_error_is_driver_unavailable() -> None:
    runner = FakeProcessRunner(exc=OSError("python missing"))

    result = read_uiautomator2_app_current(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_unavailable"
    assert "python missing" in result.error.detail


def test_uiautomator2_app_current_malformed_payload_is_app_unavailable() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=0,
            stdout='{"ok": true, "metadata": {"package": "com.example.app"}}',
            stderr="raw stdout should not be echoed",
        )
    )

    result = read_uiautomator2_app_current(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "app_unavailable"
    assert "raw stdout" not in result.error.detail


def test_uiautomator2_app_current_failed_probe_does_not_echo_stdout() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=1,
            stdout='{"ok": false, "metadata": {"secret": "value"}',
            stderr="raw stderr should not be echoed",
        )
    )

    result = read_uiautomator2_app_current(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "app_unavailable"
    assert "raw stderr" not in result.error.detail
    assert "secret" not in result.error.detail
