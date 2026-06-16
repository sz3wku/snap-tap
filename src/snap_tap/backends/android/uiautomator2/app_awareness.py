from __future__ import annotations

import sys
from collections.abc import Mapping
from time import perf_counter

from snap_tap.device.identity import normalize_serial
from snap_tap.backends.android.uiautomator2.app_awareness_payload import (
    has_required_metadata,
    probe_error_code,
    probe_error_detail,
    probe_metadata,
)
from snap_tap.backends.contracts import (
    DriverAppAwareness,
    normalize_package,
)
from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessRunner,
    ProcessTimeoutError,
    SubprocessRunner,
)
from snap_tap.backends.android.uiautomator2.probe_payload import parse_probe_payload
from snap_tap.backends.android.uiautomator2.recovery import retry_once_after_recovery


SUPPORTED_APP_OPERATIONS = frozenset({"app_current", "package_info"})


class Uiautomator2AppAwarenessReader:
    backend_name = "uiautomator2"

    def __init__(
        self,
        *,
        process_runner: ProcessRunner | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._process_runner = process_runner or SubprocessRunner()
        self._python_executable = python_executable or sys.executable

    def app_current(
        self,
        device_id: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness:
        return read_uiautomator2_app_current(
            device_id=device_id,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
            python_executable=self._python_executable,
        )

    def package_info(
        self,
        device_id: str,
        package: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness:
        return read_uiautomator2_package_info(
            device_id=device_id,
            package=package,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
            python_executable=self._python_executable,
        )


def read_uiautomator2_app_current(
    *,
    device_id: str,
    timeout_s: float = 5.0,
    process_runner: ProcessRunner | None = None,
    python_executable: str | None = None,
) -> DriverAppAwareness:
    return _run_uiautomator2_app_probe(
        operation="app_current",
        device_id=device_id,
        package=None,
        timeout_s=timeout_s,
        process_runner=process_runner,
        python_executable=python_executable,
    )


def read_uiautomator2_package_info(
    *,
    device_id: str,
    package: str,
    timeout_s: float = 5.0,
    process_runner: ProcessRunner | None = None,
    python_executable: str | None = None,
) -> DriverAppAwareness:
    return _run_uiautomator2_app_probe(
        operation="package_info",
        device_id=device_id,
        package=package,
        timeout_s=timeout_s,
        process_runner=process_runner,
        python_executable=python_executable,
    )


def _run_uiautomator2_app_probe(
    *,
    operation: str,
    device_id: str,
    package: str | None,
    timeout_s: float,
    process_runner: ProcessRunner | None,
    python_executable: str | None,
) -> DriverAppAwareness:
    started = perf_counter()
    serial = normalize_serial(device_id)
    package_name = normalize_package(package) if operation == "package_info" else None
    runner = process_runner or SubprocessRunner()
    executable = python_executable or sys.executable

    if operation not in SUPPORTED_APP_OPERATIONS:
        return _failure(
            operation=operation,
            code="unsupported_operation",
            detail=f"Unsupported app awareness operation: {operation}.",
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )
    if serial is None:
        return _failure(
            operation=operation,
            code="device_offline",
            detail="Device serial is required and must be a valid ADB serial.",
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )
    if operation == "package_info" and package_name is None:
        return _failure(
            operation=operation,
            code="app_unavailable",
            detail="Package is required and must be a valid Android package name.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )

    result = _run_uiautomator2_app_probe_once(
        operation=operation,
        serial=serial,
        package_name=package_name,
        timeout_s=timeout_s,
        runner=runner,
        executable=executable,
        started=started,
    )
    return retry_once_after_recovery(
        result,
        device_id=serial,
        operation=operation,
        process_runner=runner,
        python_executable=executable,
        retry=lambda: _run_uiautomator2_app_probe_once(
            operation=operation,
            serial=serial,
            package_name=package_name,
            timeout_s=timeout_s,
            runner=runner,
            executable=executable,
            started=started,
        ),
    )


def _run_uiautomator2_app_probe_once(
    *,
    operation: str,
    serial: str,
    package_name: str | None,
    timeout_s: float,
    runner: ProcessRunner,
    executable: str,
    started: float,
) -> DriverAppAwareness:
    args = [
        executable,
        "-m",
        "snap_tap.backends.android.uiautomator2.probes",
        operation,
        "--device",
        serial,
    ]
    if package_name is not None:
        args.extend(["--package", package_name])

    try:
        result = runner.run(args, timeout_s=timeout_s)
    except ProcessTimeoutError as exc:
        return _failure(
            operation=operation,
            code="driver_timeout",
            detail=str(exc) or f"uiautomator2 {operation} timed out.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": timeout_s},
        )
    except OSError as exc:
        return _failure(
            operation=operation,
            code="driver_unavailable",
            detail=str(exc) or f"uiautomator2 {operation} driver is unavailable.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": timeout_s},
        )

    payload = parse_probe_payload(result.stdout)
    metadata = probe_metadata(
        operation,
        payload,
        timeout_s=timeout_s,
        package_name=package_name,
    )
    if result.returncode != 0 or payload.get("ok") is not True:
        return _failure(
            operation=operation,
            code=probe_error_code(payload),
            detail=probe_error_detail(payload, operation),
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
        )
    if not has_required_metadata(operation, metadata):
        return _failure(
            operation=operation,
            code="app_unavailable",
            detail=f"uiautomator2 {operation} probe returned malformed app metadata.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
        )
    return DriverAppAwareness.success(
        device_id=serial,
        backend="uiautomator2",
        operation=operation,
        elapsed_ms=_elapsed_ms(started),
        metadata=metadata,
    )


def _failure(
    *,
    operation: str,
    code: str,
    detail: str,
    elapsed_ms: float,
    device_id: str | None = None,
    status: str = "unhealthy",
    metadata: Mapping[str, object] | None = None,
) -> DriverAppAwareness:
    return DriverAppAwareness.failure(
        backend="uiautomator2",
        operation=operation,
        code=code,
        detail=detail,
        device_id=device_id,
        elapsed_ms=elapsed_ms,
        status=status,
        metadata=metadata,
    )


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
