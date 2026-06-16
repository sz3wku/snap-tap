from __future__ import annotations

from collections.abc import Sequence

from snap_tap.backends.android.uiautomator2.lifecycle import run_uiautomator2_lifecycle
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


def test_lifecycle_rejects_malformed_serial_without_subprocess() -> None:
    runner = FakeProcessRunner()

    result = run_uiautomator2_lifecycle(
        operation="init",
        device_id="bad serial",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.status == "blocked"
    assert result.error is not None
    assert result.error.code == "device_offline"
    assert runner.calls == []


def test_lifecycle_runs_supported_operation_as_argument_list() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(returncode=0, stdout="doctor ok", stderr="")
    )

    result = run_uiautomator2_lifecycle(
        operation="doctor",
        device_id="RFCN4010FCK",
        timeout_s=3.0,
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is True
    assert result.operation == "doctor"
    assert result.metadata == {
        "returncode": "0",
        "timeout_s": "3.0",
        "stdout_present": "true",
        "stderr_present": "false",
    }
    assert runner.calls == [
        ([".venv", "-m", "uiautomator2", "-s", "RFCN4010FCK", "doctor"], 3.0)
    ]


def test_lifecycle_timeout_returns_structured_failure() -> None:
    runner = FakeProcessRunner(exc=ProcessTimeoutError("doctor timed out"))

    result = run_uiautomator2_lifecycle(
        operation="doctor",
        device_id="RFCN4010FCK",
        timeout_s=0.01,
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_timeout"


def test_lifecycle_failure_does_not_echo_stdout_or_stderr() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=1,
            stdout="raw stdout secret",
            stderr="raw stderr secret",
        )
    )

    result = run_uiautomator2_lifecycle(
        operation="doctor",
        device_id="RFCN4010FCK",
        timeout_s=3.0,
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_lifecycle_failed"
    assert result.error.detail == "uiautomator2 doctor exited with code 1."
    assert result.metadata == {
        "returncode": "1",
        "timeout_s": "3.0",
        "stdout_present": "true",
        "stderr_present": "true",
    }
    assert "raw stdout" not in result.error.detail
    assert "raw stderr" not in result.error.detail
