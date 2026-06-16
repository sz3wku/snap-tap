from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
import math
from time import perf_counter
import sys

from snap_tap.device.identity import normalize_serial
from snap_tap.backends.contracts import DriverError, DriverNavigation
from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessRunner,
    ProcessTimeoutError,
    SubprocessRunner,
)
from snap_tap.backends.android.uiautomator2.probe_payload import parse_probe_payload, probe_error_detail


NAVIGATION_BACK = "back"
NAVIGATION_HOME = "home"
NAVIGATION_SWIPE = "swipe"
NAVIGATION_OPERATIONS = {NAVIGATION_BACK, NAVIGATION_HOME, NAVIGATION_SWIPE}
SWIPE_DIRECTIONS = {"up", "down", "left", "right"}


class Uiautomator2Navigator:
    backend_name = "uiautomator2"

    def __init__(
        self,
        *,
        process_runner: ProcessRunner | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._process_runner = process_runner or SubprocessRunner()
        self._python_executable = python_executable or sys.executable

    def back(self, *, device_id: str, timeout_s: float = 10.0) -> DriverNavigation:
        return navigation_uiautomator2(
            operation=NAVIGATION_BACK,
            device_id=device_id,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
            python_executable=self._python_executable,
        )

    def home(self, *, device_id: str, timeout_s: float = 10.0) -> DriverNavigation:
        return navigation_uiautomator2(
            operation=NAVIGATION_HOME,
            device_id=device_id,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
            python_executable=self._python_executable,
        )

    def swipe(
        self,
        *,
        device_id: str,
        direction: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration_ms: int,
        distance_ratio: float,
        timeout_s: float = 10.0,
    ) -> DriverNavigation:
        return navigation_uiautomator2(
            operation=NAVIGATION_SWIPE,
            device_id=device_id,
            direction=direction,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            duration_ms=duration_ms,
            distance_ratio=distance_ratio,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
            python_executable=self._python_executable,
        )


def navigation_uiautomator2(
    *,
    operation: str,
    device_id: str,
    direction: str | None = None,
    x1: float | None = None,
    y1: float | None = None,
    x2: float | None = None,
    y2: float | None = None,
    duration_ms: int | None = None,
    distance_ratio: float | None = None,
    timeout_s: float = 10.0,
    process_runner: ProcessRunner | None = None,
    python_executable: str | None = None,
) -> DriverNavigation:
    started = perf_counter()
    serial = normalize_serial(device_id)
    runner = process_runner or SubprocessRunner()
    executable = python_executable or sys.executable
    if serial is None:
        return _failure(
            code="device_offline",
            detail="Device serial is required and must be a valid ADB serial.",
            operation=_safe_operation(operation),
            elapsed_ms=_elapsed_ms(started),
        )
    args_or_error = _probe_args(
        executable=executable,
        operation=operation,
        serial=serial,
        direction=direction,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        duration_ms=duration_ms,
        distance_ratio=distance_ratio,
    )
    if isinstance(args_or_error, DriverError):
        return _failure(
            code=args_or_error.code,
            detail=args_or_error.detail,
            operation=_safe_operation(operation),
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
        )

    try:
        result = runner.run(args_or_error, timeout_s=timeout_s)
    except ProcessTimeoutError as exc:
        return _failure(
            code="driver_timeout",
            detail=str(exc) or f"uiautomator2 {operation} timed out.",
            operation=_safe_operation(operation),
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=_metadata(
                operation=operation,
                timeout_s=timeout_s,
                direction=direction,
                distance_ratio=distance_ratio,
                duration_ms=duration_ms,
                touch_may_have_occurred=True,
            ),
            attempted=True,
        )
    except OSError as exc:
        return _failure(
            code="driver_unavailable",
            detail=str(exc) or f"uiautomator2 {operation} driver is unavailable.",
            operation=_safe_operation(operation),
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=_metadata(
                operation=operation,
                timeout_s=timeout_s,
                direction=direction,
                distance_ratio=distance_ratio,
                duration_ms=duration_ms,
            ),
        )

    payload = parse_probe_payload(result.stdout)
    metadata = _probe_metadata(
        payload,
        operation=operation,
        timeout_s=timeout_s,
        direction=direction,
        distance_ratio=distance_ratio,
        duration_ms=duration_ms,
    )
    confirmed = _confirmed_value(payload, operation=operation)
    if result.returncode != 0 or payload.get("ok") is not True:
        return _failure(
            code=_probe_error_code(payload),
            detail=probe_error_detail(payload, operation=operation),
            operation=_safe_operation(operation),
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=_with_ambiguous_touch(metadata),
            attempted=True,
        )
    if not isinstance(confirmed, bool):
        return _failure(
            code="driver_probe_failed",
            detail=f"uiautomator2 {operation} probe omitted confirmation.",
            operation=_safe_operation(operation),
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=_with_ambiguous_touch(metadata),
            attempted=True,
        )
    return DriverNavigation(
        ok=True,
        status="completed",
        device_id=serial,
        backend="uiautomator2",
        operation=_safe_operation(operation),
        elapsed_ms=_elapsed_ms(started),
        attempted=True,
        confirmed=confirmed,
        checked_at=_utc_now(),
        metadata=metadata,
    )


def _probe_args(
    *,
    executable: str,
    operation: str,
    serial: str,
    direction: str | None,
    x1: float | None,
    y1: float | None,
    x2: float | None,
    y2: float | None,
    duration_ms: int | None,
    distance_ratio: float | None,
) -> list[str] | DriverError:
    if operation not in NAVIGATION_OPERATIONS:
        return DriverError(
            code="unsupported_operation",
            detail="Navigation operation must be back, home, or swipe.",
        )
    args = [
        executable,
        "-m",
        "snap_tap.backends.android.uiautomator2.navigation_probe",
        operation,
        "--device",
        serial,
    ]
    if operation != NAVIGATION_SWIPE:
        return args
    if direction not in SWIPE_DIRECTIONS:
        return DriverError(
            code="invalid_arguments",
            detail="Swipe direction must be up, down, left, or right.",
        )
    if (
        not _valid_coordinate(x1)
        or not _valid_coordinate(y1)
        or not _valid_coordinate(x2)
        or not _valid_coordinate(y2)
        or not isinstance(duration_ms, int)
        or duration_ms <= 0
    ):
        return DriverError(
            code="invalid_arguments",
            detail="Swipe driver coordinates and duration must be valid.",
        )
    assert x1 is not None
    assert y1 is not None
    assert x2 is not None
    assert y2 is not None
    swipe_x1 = float(x1)
    swipe_y1 = float(y1)
    swipe_x2 = float(x2)
    swipe_y2 = float(y2)
    args.extend(
        [
            "--direction",
            direction,
            "--x1",
            str(round(swipe_x1, 3)),
            "--y1",
            str(round(swipe_y1, 3)),
            "--x2",
            str(round(swipe_x2, 3)),
            "--y2",
            str(round(swipe_y2, 3)),
            "--duration-ms",
            str(duration_ms),
        ]
    )
    if distance_ratio is not None:
        args.extend(["--distance-ratio", str(round(distance_ratio, 3))])
    return args


def _failure(
    *,
    code: str,
    detail: str,
    operation: str,
    elapsed_ms: float,
    device_id: str | None = None,
    metadata: Mapping[str, object] | None = None,
    attempted: bool = False,
) -> DriverNavigation:
    return DriverNavigation(
        ok=False,
        status="failed",
        device_id=device_id,
        backend="uiautomator2",
        operation=operation,
        elapsed_ms=elapsed_ms,
        attempted=attempted,
        confirmed=False,
        checked_at=_utc_now(),
        metadata=metadata or {},
        error=DriverError(code=code, detail=detail),
    )


def _confirmed_value(payload: Mapping[str, object], *, operation: str) -> object:
    if operation in {NAVIGATION_BACK, NAVIGATION_HOME}:
        return payload.get("pressed")
    if operation == NAVIGATION_SWIPE:
        return payload.get("swiped")
    return None


def _probe_error_code(payload: Mapping[str, object]) -> str:
    error = payload.get("error")
    if not isinstance(error, Mapping):
        return "navigation_failed"
    code = error.get("code")
    return code if isinstance(code, str) and code else "navigation_failed"


def _probe_metadata(
    payload: Mapping[str, object],
    *,
    operation: str,
    timeout_s: float,
    direction: str | None,
    distance_ratio: float | None,
    duration_ms: int | None,
) -> dict[str, object]:
    metadata = _metadata(
        operation=operation,
        timeout_s=timeout_s,
        direction=direction,
        distance_ratio=distance_ratio,
        duration_ms=duration_ms,
    )
    raw = payload.get("metadata")
    if isinstance(raw, Mapping):
        for key in ("touch_may_have_occurred", "press_returned", "swipe_returned"):
            value = raw.get(key)
            if isinstance(value, bool):
                metadata[key] = value
    return metadata


def _metadata(
    *,
    operation: str,
    timeout_s: float,
    direction: str | None = None,
    distance_ratio: float | None = None,
    duration_ms: int | None = None,
    touch_may_have_occurred: bool | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "operation": _safe_operation(operation),
        "timeout_s": str(timeout_s),
    }
    if direction in SWIPE_DIRECTIONS:
        metadata["direction"] = direction
    if _valid_ratio(distance_ratio):
        assert distance_ratio is not None
        metadata["distance_ratio"] = round(distance_ratio, 3)
    if isinstance(duration_ms, int) and not isinstance(duration_ms, bool):
        metadata["duration_ms"] = duration_ms
    if touch_may_have_occurred is not None:
        metadata["touch_may_have_occurred"] = touch_may_have_occurred
    return metadata


def _with_ambiguous_touch(metadata: Mapping[str, object]) -> dict[str, object]:
    updated = dict(metadata)
    if "touch_may_have_occurred" not in updated:
        updated["touch_may_have_occurred"] = True
    return updated


def _safe_operation(operation: str) -> str:
    return operation if operation in NAVIGATION_OPERATIONS else NAVIGATION_BACK


def _valid_coordinate(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and (
        math.isfinite(float(value)) and float(value) >= 0
    )


def _valid_ratio(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and (
        math.isfinite(float(value)) and float(value) > 0
    )


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
