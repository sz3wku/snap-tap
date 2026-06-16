from __future__ import annotations

from collections.abc import Sequence

from snap_tap.backends.android.uiautomator2.backend import Uiautomator2Backend
from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessResult,
    ProcessRunner,
)
from snap_tap.backends.android.uiautomator2.recovery import retry_once_after_recovery
from snap_tap.backends.android.uiautomator2.xml_dump import dump_uiautomator2_xml
from snap_tap.backends.contracts import DriverHealth


class SequenceProcessRunner(ProcessRunner):
    def __init__(self, outcomes: Sequence[ProcessResult | Exception]) -> None:
        self.calls: list[tuple[list[str], float]] = []
        self._outcomes = list(outcomes)

    def run(self, args: Sequence[str], timeout_s: float) -> ProcessResult:
        self.calls.append((list(args), timeout_s))
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_health_recovers_driver_unavailable_once() -> None:
    runner = SequenceProcessRunner(
        [
            _failure_payload("driver_unavailable", "jsonrpc down"),
            ProcessResult(returncode=0, stdout="init ok", stderr=""),
            ProcessResult(
                returncode=0,
                stdout='{"ok": true, "metadata": {"model": "SM-G981B"}}',
                stderr="",
            ),
        ]
    )

    health = Uiautomator2Backend(
        process_runner=runner,
        python_executable=".venv",
    ).health("RFCN4010FCK", timeout_s=2.0)

    assert health.ok is True
    assert health.metadata["model"] == "SM-G981B"
    assert health.metadata["attempt"] == 2
    assert health.metadata["recovery_attempted"] is True
    assert health.metadata["recovery_ok"] is True
    assert health.metadata["recovered_after_failure"] == "driver_unavailable"
    assert [call[0][2] for call in runner.calls] == [
        "snap_tap.backends.android.uiautomator2.probes",
        "uiautomator2",
        "snap_tap.backends.android.uiautomator2.probes",
    ]


def test_failed_recovery_does_not_loop() -> None:
    runner = SequenceProcessRunner(
        [
            _failure_payload("driver_unavailable", "jsonrpc down"),
            ProcessResult(returncode=1, stdout="", stderr="init failed"),
        ]
    )

    health = Uiautomator2Backend(
        process_runner=runner,
        python_executable=".venv",
    ).health("RFCN4010FCK", timeout_s=2.0)

    assert health.ok is False
    assert health.error is not None
    assert health.error.code == "driver_unavailable"
    assert health.metadata["attempt"] == 1
    assert health.metadata["recovery_attempted"] is True
    assert health.metadata["recovery_ok"] is False
    assert health.metadata["recovery_error_code"] == "driver_lifecycle_failed"
    assert len(runner.calls) == 2


def test_malformed_health_probe_does_not_recover() -> None:
    runner = SequenceProcessRunner(
        [ProcessResult(returncode=1, stdout="not-json", stderr="raw stderr")]
    )

    health = Uiautomator2Backend(
        process_runner=runner,
        python_executable=".venv",
    ).health("RFCN4010FCK", timeout_s=2.0)

    assert health.ok is False
    assert health.error is not None
    assert health.error.code == "driver_probe_failed"
    assert health.error.recoverable is False
    assert len(runner.calls) == 1


def test_malformed_structured_health_error_does_not_recover() -> None:
    runner = SequenceProcessRunner(
        [
            ProcessResult(
                returncode=1,
                stdout='{"ok": false, "error": {"detail": "missing code"}}',
                stderr="raw stderr",
            )
        ]
    )

    health = Uiautomator2Backend(
        process_runner=runner,
        python_executable=".venv",
    ).health("RFCN4010FCK", timeout_s=2.0)

    assert health.ok is False
    assert health.error is not None
    assert health.error.code == "driver_probe_failed"
    assert health.error.recoverable is False
    assert len(runner.calls) == 1


def test_recovery_helper_blocks_unsupported_operations() -> None:
    runner = SequenceProcessRunner(
        [ProcessResult(returncode=0, stdout="init ok", stderr="")]
    )
    first = DriverHealth.failure(
        backend="uiautomator2",
        code="driver_unavailable",
        detail="bridge down",
        device_id="RFCN4010FCK",
        elapsed_ms=1.0,
    )

    result = retry_once_after_recovery(
        first,
        device_id="RFCN4010FCK",
        operation="tap",
        process_runner=runner,
        python_executable=".venv",
        retry=lambda: DriverHealth.success(
            device_id="RFCN4010FCK",
            backend="uiautomator2",
            elapsed_ms=2.0,
        ),
    )

    assert result is first
    assert runner.calls == []


def test_recovery_helper_settles_after_successful_init_before_retry() -> None:
    runner = SequenceProcessRunner(
        [ProcessResult(returncode=0, stdout="init ok", stderr="")]
    )
    events: list[tuple[str, float]] = []
    first = DriverHealth.failure(
        backend="uiautomator2",
        code="driver_unavailable",
        detail="bridge down",
        device_id="RFCN4010FCK",
        elapsed_ms=1.0,
    )

    def sleeper(seconds: float) -> None:
        events.append(("sleep", seconds))

    def retry() -> DriverHealth:
        events.append(("retry", 0.0))
        return DriverHealth.success(
            device_id="RFCN4010FCK",
            backend="uiautomator2",
            elapsed_ms=2.0,
        )

    result = retry_once_after_recovery(
        first,
        device_id="RFCN4010FCK",
        operation="screenshot",
        process_runner=runner,
        python_executable=".venv",
        retry=retry,
        recovery_settle_s=0.75,
        sleeper=sleeper,
    )

    assert result.ok is True
    assert result.metadata["attempt"] == 2
    assert events == [("sleep", 0.75), ("retry", 0.0)]
    assert len(runner.calls) == 1


def test_dump_xml_recovers_driver_unavailable_then_retries() -> None:
    runner = SequenceProcessRunner(
        [
            _failure_payload("driver_unavailable", "bridge down"),
            ProcessResult(returncode=0, stdout="init ok", stderr=""),
            ProcessResult(
                returncode=0,
                stdout='{"ok": true, "xml": "<hierarchy><node /></hierarchy>"}',
                stderr="",
            ),
        ]
    )

    result = dump_uiautomator2_xml(
        device_id="RFCN4010FCK",
        timeout_s=3.0,
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is True
    assert result.xml == "<hierarchy><node /></hierarchy>"
    assert result.metadata["attempt"] == 2
    assert result.metadata["recovery_ok"] is True
    assert [call[0][2] for call in runner.calls] == [
        "snap_tap.backends.android.uiautomator2.probes",
        "uiautomator2",
        "snap_tap.backends.android.uiautomator2.probes",
    ]


def _failure_payload(code: str, detail: str) -> ProcessResult:
    return ProcessResult(
        returncode=1,
        stdout=f'{{"ok": false, "error": {{"code": "{code}", "detail": "{detail}"}}}}',
        stderr="raw stderr must not leak",
    )
