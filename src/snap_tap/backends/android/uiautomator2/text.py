from __future__ import annotations

import math
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from time import perf_counter

from snap_tap.backends.android.uiautomator2.probe_payload import (
    parse_probe_payload,
    probe_error_detail,
)
from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessRunner,
    ProcessTimeoutError,
    SubprocessRunner,
)
from snap_tap.backends.contracts import DriverError, DriverText
from snap_tap.device.identity import normalize_serial

TEXT_INPUT_MODE = "input"
TEXT_REPLACE_MODE = "replace_text"
TEXT_MODES = {TEXT_INPUT_MODE, TEXT_REPLACE_MODE}


class Uiautomator2Texter:
    backend_name = "uiautomator2"

    def __init__(
        self,
        *,
        process_runner: ProcessRunner | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._process_runner = process_runner or SubprocessRunner()
        self._python_executable = python_executable or sys.executable

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
        return text_uiautomator2(
            device_id=device_id,
            x=x,
            y=y,
            text=text,
            mode=mode,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
            python_executable=self._python_executable,
        )


def text_uiautomator2(
    *,
    device_id: str,
    x: float,
    y: float,
    text: str,
    mode: str,
    timeout_s: float = 10.0,
    process_runner: ProcessRunner | None = None,
    python_executable: str | None = None,
) -> DriverText:
    started = perf_counter()
    serial = normalize_serial(device_id)
    runner = process_runner or SubprocessRunner()
    executable = python_executable or sys.executable
    normalized = _normalized_text(text)
    if serial is None:
        return _failure(
            code="device_offline",
            detail="Device serial is required and must be a valid ADB serial.",
            operation=mode if mode in TEXT_MODES else TEXT_INPUT_MODE,
            elapsed_ms=_elapsed_ms(started),
        )
    if mode not in TEXT_MODES:
        return _failure(
            code="invalid_arguments",
            detail="Text input mode must be input or replace_text.",
            operation=mode,
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
        )
    if normalized is None:
        return _failure(
            code="input_failed",
            detail="Text payload must be non-empty normalized text.",
            operation=mode,
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
        )
    if not _valid_coordinate(x) or not _valid_coordinate(y):
        return _failure(
            code="input_failed",
            detail="Text target coordinates must be finite non-negative numbers.",
            operation=mode,
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
        )

    args = [
        executable,
        "-m",
        "snap_tap.backends.android.uiautomator2.probes",
        "input_text" if mode == TEXT_INPUT_MODE else "replace_text",
        "--device",
        serial,
        "--x",
        str(round(float(x), 3)),
        "--y",
        str(round(float(y), 3)),
        "--text",
        normalized,
    ]
    try:
        result = runner.run(args, timeout_s=timeout_s)
    except ProcessTimeoutError as exc:
        return _failure(
            code="driver_timeout",
            detail=str(exc) or "uiautomator2 text input timed out.",
            operation=mode,
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={
                "timeout_s": str(timeout_s),
                "touch_may_have_occurred": True,
                "text_length": len(normalized),
            },
            attempted=True,
        )
    except OSError as exc:
        return _failure(
            code="driver_unavailable",
            detail=str(exc) or "uiautomator2 text input driver is unavailable.",
            operation=mode,
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": str(timeout_s), "text_length": len(normalized)},
        )

    payload = parse_probe_payload(result.stdout)
    metadata = _probe_metadata(payload, timeout_s=timeout_s, text=normalized)
    applied = payload.get("text_applied")
    if result.returncode != 0 or payload.get("ok") is not True:
        metadata = _with_ambiguous_child_touch(metadata)
        return _failure(
            code=_probe_error_code(payload),
            detail=probe_error_detail(
                payload,
                operation=mode,
                sensitive_markers=(normalized,),
            ),
            operation=mode,
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
            attempted=True,
        )
    if not isinstance(applied, bool):
        metadata = _with_ambiguous_child_touch(metadata)
        return _failure(
            code="driver_probe_failed",
            detail="uiautomator2 text probe omitted text_applied confirmation.",
            operation=mode,
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
            attempted=True,
        )
    return DriverText(
        ok=True,
        status="completed",
        device_id=serial,
        backend="uiautomator2",
        operation=mode,
        elapsed_ms=_elapsed_ms(started),
        attempted=True,
        confirmed=applied,
        checked_at=_utc_now(),
        metadata=metadata,
    )


def _failure(
    *,
    code: str,
    detail: str,
    operation: str,
    elapsed_ms: float,
    device_id: str | None = None,
    metadata: Mapping[str, object] | None = None,
    attempted: bool = False,
) -> DriverText:
    return DriverText(
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


def _probe_error_code(payload: Mapping[str, object]) -> str:
    error = payload.get("error")
    if not isinstance(error, Mapping):
        return "input_failed"
    code = error.get("code")
    return code if isinstance(code, str) and code else "input_failed"


def _probe_metadata(
    payload: Mapping[str, object],
    *,
    timeout_s: float,
    text: str,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "timeout_s": str(timeout_s),
        "text_length": len(text),
    }
    raw = payload.get("metadata")
    if not isinstance(raw, Mapping):
        return metadata
    _copy_bool_metadata(
        raw,
        metadata,
        "replace",
        "text_call_returned",
        "text_verified",
        "touch_may_have_occurred",
    )
    _copy_int_metadata(raw, metadata, "before_text_length", "after_text_length")
    _copy_enum_metadata(
        raw,
        metadata,
        key="input_method",
        allowed={"set_input_ime", "set_fastinput_ime", "unavailable"},
    )
    _copy_enum_metadata(
        raw,
        metadata,
        key="stage",
        allowed={
            "connect",
            "input_method",
            "click",
            "before_verify",
            "send_text",
            "after_verify",
        },
    )
    return metadata


def _with_ambiguous_child_touch(metadata: Mapping[str, object]) -> dict[str, object]:
    updated = dict(metadata)
    if "touch_may_have_occurred" not in updated:
        updated["touch_may_have_occurred"] = True
    return updated


def _copy_bool_metadata(
    source: Mapping[str, object],
    target: dict[str, object],
    *keys: str,
) -> None:
    for key in keys:
        value = source.get(key)
        if isinstance(value, bool):
            target[key] = value


def _copy_int_metadata(
    source: Mapping[str, object],
    target: dict[str, object],
    *keys: str,
) -> None:
    for key in keys:
        value = source.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            target[key] = value


def _copy_enum_metadata(
    source: Mapping[str, object],
    target: dict[str, object],
    *,
    key: str,
    allowed: set[str],
) -> None:
    value = source.get(key)
    if isinstance(value, str) and value in allowed:
        target[key] = value


def _normalized_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if not value or not value.strip() or len(value) > 4096:
        return None
    if "\x00" in value:
        return None
    return value


def _valid_coordinate(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and (
        math.isfinite(float(value)) and float(value) >= 0
    )


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
