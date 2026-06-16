from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any, Protocol, TypeVar, cast

from snap_tap.backends.contracts import DriverError, is_driver_recoverable
from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessRunner,
    ProcessTimeoutError,
)


DEFAULT_RECOVERY_TIMEOUT_S = 30.0
RECOVERABLE_READ_OPERATIONS = frozenset(
    {
        "health",
        "dump_xml",
        "screenshot",
        "app_current",
        "package_info",
    }
)


class DriverResult(Protocol):
    @property
    def ok(self) -> bool: ...

    @property
    def error(self) -> DriverError | None: ...

    @property
    def metadata(self) -> Mapping[str, object]: ...


ResultT = TypeVar("ResultT", bound=DriverResult)


@dataclass(frozen=True)
class RecoveryResult:
    ok: bool
    operation: str
    elapsed_ms: float
    error: DriverError | None = None


def retry_once_after_recovery(
    first_result: ResultT,
    *,
    device_id: str,
    operation: str,
    process_runner: ProcessRunner,
    python_executable: str,
    retry: Callable[[], ResultT],
    recovery_timeout_s: float = DEFAULT_RECOVERY_TIMEOUT_S,
) -> ResultT:
    if (
        first_result.ok
        or first_result.error is None
        or operation not in RECOVERABLE_READ_OPERATIONS
        or not is_driver_recoverable(first_result.error.code)
    ):
        return first_result

    recovery = run_uiautomator2_recovery(
        device_id=device_id,
        process_runner=process_runner,
        python_executable=python_executable,
        timeout_s=recovery_timeout_s,
    )
    if not recovery.ok:
        return _with_recovery_metadata(
            first_result,
            recovery,
            recovered_after_failure=first_result.error.code,
            attempt=1,
        )

    retried = retry()
    return _with_recovery_metadata(
        retried,
        recovery,
        recovered_after_failure=first_result.error.code,
        attempt=2,
    )


def run_uiautomator2_recovery(
    *,
    device_id: str,
    process_runner: ProcessRunner,
    python_executable: str,
    timeout_s: float = DEFAULT_RECOVERY_TIMEOUT_S,
) -> RecoveryResult:
    started = perf_counter()
    args = [
        python_executable,
        "-m",
        "uiautomator2",
        "-s",
        device_id,
        "init",
    ]
    try:
        result = process_runner.run(args, timeout_s=timeout_s)
    except ProcessTimeoutError as exc:
        return RecoveryResult(
            ok=False,
            operation="init",
            elapsed_ms=_elapsed_ms(started),
            error=DriverError(
                code="driver_timeout",
                detail=str(exc) or "uiautomator2 recovery init timed out.",
            ),
        )
    except OSError as exc:
        return RecoveryResult(
            ok=False,
            operation="init",
            elapsed_ms=_elapsed_ms(started),
            error=DriverError(
                code="driver_unavailable",
                detail=str(exc) or "uiautomator2 recovery init is unavailable.",
            ),
        )

    if result.returncode == 0:
        return RecoveryResult(
            ok=True,
            operation="init",
            elapsed_ms=_elapsed_ms(started),
        )
    return RecoveryResult(
        ok=False,
        operation="init",
        elapsed_ms=_elapsed_ms(started),
        error=DriverError(
            code="driver_lifecycle_failed",
            detail="uiautomator2 recovery init failed with nonzero exit.",
        ),
    )


def _with_recovery_metadata(
    result: ResultT,
    recovery: RecoveryResult,
    *,
    recovered_after_failure: str,
    attempt: int,
) -> ResultT:
    metadata = dict(result.metadata)
    metadata.update(
        {
            "attempt": attempt,
            "recovery_attempted": True,
            "recovery_ok": recovery.ok,
            "recovery_operation": recovery.operation,
            "recovery_elapsed_ms": recovery.elapsed_ms,
            "recovered_after_failure": recovered_after_failure,
        }
    )
    if recovery.error is not None:
        metadata["recovery_error_code"] = recovery.error.code
    return cast(ResultT, replace(cast(Any, result), metadata=metadata))


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
