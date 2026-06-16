from __future__ import annotations

import sys
from time import perf_counter

from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessRunner,
    ProcessTimeoutError,
    SubprocessRunner,
)
from snap_tap.backends.contracts import DriverLifecycleResult
from snap_tap.device.identity import normalize_serial

SUPPORTED_LIFECYCLE_OPERATIONS = frozenset({"init", "doctor"})


class Uiautomator2LifecycleRunner:
    backend_name = "uiautomator2"

    def __init__(
        self,
        *,
        process_runner: ProcessRunner | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._process_runner = process_runner or SubprocessRunner()
        self._python_executable = python_executable or sys.executable

    def run(
        self,
        *,
        operation: str,
        device_id: str,
        timeout_s: float = 60.0,
    ) -> DriverLifecycleResult:
        return run_uiautomator2_lifecycle(
            operation=operation,
            device_id=device_id,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
            python_executable=self._python_executable,
        )


def run_uiautomator2_lifecycle(
    *,
    operation: str,
    device_id: str,
    timeout_s: float = 60.0,
    process_runner: ProcessRunner | None = None,
    python_executable: str | None = None,
) -> DriverLifecycleResult:
    started = perf_counter()
    serial = normalize_serial(device_id)
    runner = process_runner or SubprocessRunner()
    executable = python_executable or sys.executable

    if operation not in SUPPORTED_LIFECYCLE_OPERATIONS:
        return DriverLifecycleResult.failure(
            backend="uiautomator2",
            operation=operation,
            code="unsupported_operation",
            detail=f"Unsupported mobile lifecycle operation: {operation}.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )
    if serial is None:
        return DriverLifecycleResult.failure(
            backend="uiautomator2",
            operation=operation,
            code="device_offline",
            detail="Device serial is required and must be a valid ADB serial.",
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )

    args = [executable, "-m", "uiautomator2", "-s", serial, operation]
    try:
        result = runner.run(args, timeout_s=timeout_s)
    except ProcessTimeoutError as exc:
        return DriverLifecycleResult.failure(
            backend="uiautomator2",
            operation=operation,
            code="driver_timeout",
            detail=str(exc) or f"uiautomator2 {operation} timed out.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
        )
    except OSError:
        return DriverLifecycleResult.failure(
            backend="uiautomator2",
            operation=operation,
            code="driver_unavailable",
            detail=f"uiautomator2 {operation} driver is unavailable.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": str(timeout_s)},
        )

    metadata = {
        "returncode": str(result.returncode),
        "timeout_s": str(timeout_s),
        "stdout_present": str(bool(result.stdout.strip())).lower(),
        "stderr_present": str(bool(result.stderr.strip())).lower(),
    }
    if result.returncode == 0:
        return DriverLifecycleResult.success(
            device_id=serial,
            backend="uiautomator2",
            operation=operation,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
        )
    return DriverLifecycleResult.failure(
        backend="uiautomator2",
        operation=operation,
        code="driver_lifecycle_failed",
        detail=_failure_detail(operation, result.returncode),
        device_id=serial,
        elapsed_ms=_elapsed_ms(started),
        metadata=metadata,
    )


def _failure_detail(operation: str, returncode: int) -> str:
    return f"uiautomator2 {operation} exited with code {returncode}."


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
