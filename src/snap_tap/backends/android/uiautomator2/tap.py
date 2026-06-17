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
from snap_tap.backends.contracts import (
    DriverError,
    DriverTap,
    DriverTapXmlDump,
    DriverXmlDump,
)
from snap_tap.device.identity import normalize_serial


class Uiautomator2Tapper:
    backend_name = "uiautomator2"

    def __init__(
        self,
        *,
        process_runner: ProcessRunner | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._process_runner = process_runner or SubprocessRunner()
        self._python_executable = python_executable or sys.executable

    def tap(
        self,
        *,
        device_id: str,
        x: float,
        y: float,
        timeout_s: float = 10.0,
    ) -> DriverTap:
        return tap_uiautomator2(
            device_id=device_id,
            x=x,
            y=y,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
            python_executable=self._python_executable,
        )

    def tap_and_dump_xml(
        self,
        *,
        device_id: str,
        x: float,
        y: float,
        settle_ms: int = 0,
        timeout_s: float = 10.0,
    ) -> DriverTapXmlDump:
        return tap_and_dump_uiautomator2_xml(
            device_id=device_id,
            x=x,
            y=y,
            settle_ms=settle_ms,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
            python_executable=self._python_executable,
        )


def tap_uiautomator2(
    *,
    device_id: str,
    x: float,
    y: float,
    timeout_s: float = 10.0,
    process_runner: ProcessRunner | None = None,
    python_executable: str | None = None,
) -> DriverTap:
    started = perf_counter()
    serial = normalize_serial(device_id)
    runner = process_runner or SubprocessRunner()
    executable = python_executable or sys.executable
    if serial is None:
        return _failure(
            code="device_offline",
            detail="Device serial is required and must be a valid ADB serial.",
            elapsed_ms=_elapsed_ms(started),
        )
    if not _valid_coordinate(x) or not _valid_coordinate(y):
        return _failure(
            code="tap_failed",
            detail="Tap coordinates must be finite non-negative numbers.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
        )

    args = [
        executable,
        "-m",
        "snap_tap.backends.android.uiautomator2.probes",
        "tap",
        "--device",
        serial,
        "--x",
        str(round(float(x), 3)),
        "--y",
        str(round(float(y), 3)),
    ]
    try:
        result = runner.run(args, timeout_s=timeout_s)
    except ProcessTimeoutError as exc:
        return _failure(
            code="driver_timeout",
            detail=str(exc) or "uiautomator2 tap timed out.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={
                "timeout_s": str(timeout_s),
                "touch_may_have_occurred": True,
            },
            attempted=True,
        )
    except OSError as exc:
        return _failure(
            code="driver_unavailable",
            detail=str(exc) or "uiautomator2 tap driver is unavailable.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": str(timeout_s)},
        )

    payload = parse_probe_payload(result.stdout)
    metadata = _probe_metadata(payload, timeout_s=timeout_s)
    clicked = payload.get("clicked")
    if result.returncode != 0 or payload.get("ok") is not True:
        return _failure(
            code=_probe_error_code(payload),
            detail=probe_error_detail(payload, operation="tap"),
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
            attempted=True,
        )
    if not isinstance(clicked, bool):
        return _failure(
            code="driver_probe_failed",
            detail="uiautomator2 tap probe omitted clicked confirmation.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
            attempted=True,
        )
    return DriverTap(
        ok=True,
        status="completed",
        device_id=serial,
        backend="uiautomator2",
        operation="tap",
        elapsed_ms=_elapsed_ms(started),
        attempted=True,
        confirmed=clicked,
        checked_at=_utc_now(),
        metadata=metadata,
    )


def tap_and_dump_uiautomator2_xml(
    *,
    device_id: str,
    x: float,
    y: float,
    settle_ms: int = 0,
    timeout_s: float = 10.0,
    process_runner: ProcessRunner | None = None,
    python_executable: str | None = None,
) -> DriverTapXmlDump:
    started = perf_counter()
    serial = normalize_serial(device_id)
    runner = process_runner or SubprocessRunner()
    executable = python_executable or sys.executable
    if serial is None:
        return DriverTapXmlDump(
            tap=_failure(
                code="device_offline",
                detail="Device serial is required and must be a valid ADB serial.",
                elapsed_ms=_elapsed_ms(started),
            )
        )
    if not _valid_coordinate(x) or not _valid_coordinate(y):
        return DriverTapXmlDump(
            tap=_failure(
                code="tap_failed",
                detail="Tap coordinates must be finite non-negative numbers.",
                device_id=serial,
                elapsed_ms=_elapsed_ms(started),
            )
        )
    if not _valid_settle_ms(settle_ms):
        return DriverTapXmlDump(
            tap=_failure(
                code="tap_failed",
                detail="Post-action settle must be a non-negative integer.",
                device_id=serial,
                elapsed_ms=_elapsed_ms(started),
            )
        )

    args = [
        executable,
        "-m",
        "snap_tap.backends.android.uiautomator2.probes",
        "tap_after_xml",
        "--device",
        serial,
        "--x",
        str(round(float(x), 3)),
        "--y",
        str(round(float(y), 3)),
        "--settle-ms",
        str(settle_ms),
    ]
    try:
        result = runner.run(args, timeout_s=timeout_s)
    except ProcessTimeoutError as exc:
        return DriverTapXmlDump(
            tap=_failure(
                code="driver_timeout",
                detail=str(exc) or "uiautomator2 tap_after_xml timed out.",
                device_id=serial,
                elapsed_ms=_elapsed_ms(started),
                metadata={
                    "timeout_s": str(timeout_s),
                    "touch_may_have_occurred": True,
                },
                attempted=True,
            )
        )
    except OSError as exc:
        return DriverTapXmlDump(
            tap=_failure(
                code="driver_unavailable",
                detail=str(exc) or "uiautomator2 tap_after_xml driver is unavailable.",
                device_id=serial,
                elapsed_ms=_elapsed_ms(started),
                metadata={"timeout_s": str(timeout_s)},
            )
        )

    payload = parse_probe_payload(result.stdout)
    metadata = _probe_metadata(payload, timeout_s=timeout_s)
    clicked = payload.get("clicked")
    if result.returncode != 0 or payload.get("ok") is not True:
        return _failed_combined_result(
            payload,
            metadata=metadata,
            clicked=clicked,
            serial=serial,
            started=started,
        )
    if not isinstance(clicked, bool):
        return DriverTapXmlDump(
            tap=_failure(
                code="driver_probe_failed",
                detail="uiautomator2 tap_after_xml probe omitted clicked confirmation.",
                device_id=serial,
                elapsed_ms=_elapsed_ms(started),
                metadata=metadata,
                attempted=True,
            )
        )

    xml = payload.get("xml")
    tap = _success(serial=serial, clicked=clicked, elapsed_ms=_elapsed_ms(started), metadata=metadata)
    if not isinstance(xml, str) or not xml.strip():
        return DriverTapXmlDump(
            tap=tap,
            xml_dump=DriverXmlDump.failure(
                backend="uiautomator2",
                code="dump_failed",
                detail="uiautomator2 tap_after_xml probe returned empty XML.",
                device_id=serial,
                elapsed_ms=_elapsed_ms(started),
                metadata=metadata,
            ),
        )

    return DriverTapXmlDump(
        tap=tap,
        xml_dump=DriverXmlDump.success(
            device_id=serial,
            backend="uiautomator2",
            elapsed_ms=_elapsed_ms(started),
            xml=xml,
            metadata={**_xml_metadata(xml), **metadata},
        ),
    )


def _failure(
    *,
    code: str,
    detail: str,
    elapsed_ms: float,
    device_id: str | None = None,
    metadata: Mapping[str, object] | None = None,
    attempted: bool = False,
) -> DriverTap:
    return DriverTap(
        ok=False,
        status="failed",
        device_id=device_id,
        backend="uiautomator2",
        operation="tap",
        elapsed_ms=elapsed_ms,
        attempted=attempted,
        confirmed=False,
        checked_at=_utc_now(),
        metadata=metadata or {},
        error=DriverError(code=code, detail=detail),
    )


def _success(
    *,
    serial: str,
    clicked: bool,
    elapsed_ms: float,
    metadata: Mapping[str, object],
) -> DriverTap:
    return DriverTap(
        ok=True,
        status="completed",
        device_id=serial,
        backend="uiautomator2",
        operation="tap",
        elapsed_ms=elapsed_ms,
        attempted=True,
        confirmed=clicked,
        checked_at=_utc_now(),
        metadata=metadata,
    )


def _failed_combined_result(
    payload: Mapping[str, object],
    *,
    metadata: Mapping[str, object],
    clicked: object,
    serial: str,
    started: float,
) -> DriverTapXmlDump:
    metadata_clicked = metadata.get("clicked")
    if clicked is True or metadata_clicked is True:
        tap = _success(
            serial=serial,
            clicked=True,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
        )
        return DriverTapXmlDump(
            tap=tap,
            xml_dump=DriverXmlDump.failure(
                backend="uiautomator2",
                code=_probe_error_code(payload),
                detail=probe_error_detail(payload, operation="dump_xml"),
                device_id=serial,
                elapsed_ms=_elapsed_ms(started),
                metadata=metadata,
            ),
        )
    return DriverTapXmlDump(
        tap=_failure(
            code=_probe_error_code(payload),
            detail=probe_error_detail(payload, operation="tap"),
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
            attempted=metadata.get("touch_may_have_occurred") is True,
        )
    )


def _probe_error_code(payload: Mapping[str, object]) -> str:
    error = payload.get("error")
    if not isinstance(error, Mapping):
        return "tap_failed"
    code = error.get("code")
    return code if isinstance(code, str) and code else "tap_failed"


def _probe_metadata(
    payload: Mapping[str, object],
    *,
    timeout_s: float,
) -> dict[str, object]:
    metadata: dict[str, object] = {"timeout_s": str(timeout_s)}
    raw = payload.get("metadata")
    if isinstance(raw, Mapping):
        for key, value in raw.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                metadata[str(key)] = value
    return metadata


def _valid_coordinate(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and (
        math.isfinite(float(value)) and float(value) >= 0
    )


def _valid_settle_ms(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _xml_metadata(xml: str) -> dict[str, str]:
    return {
        "byte_length": str(len(xml.encode("utf-8"))),
        "node_count": str(xml.count("<node")),
    }


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
