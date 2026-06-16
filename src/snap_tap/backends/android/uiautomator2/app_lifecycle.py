from __future__ import annotations

import re
from collections.abc import Mapping
from time import perf_counter

from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessRunner,
    ProcessTimeoutError,
    SubprocessRunner,
)
from snap_tap.backends.contracts import (
    DriverAppCatalog,
    DriverAppEntry,
    DriverAppOpen,
    DriverError,
    normalize_package,
)
from snap_tap.device.identity import normalize_serial

_COMPONENT_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*)/(\S+)\s*$"
)


class Uiautomator2AppLifecycle:
    backend_name = "uiautomator2"

    def __init__(
        self,
        *,
        process_runner: ProcessRunner | None = None,
    ) -> None:
        self._process_runner = process_runner or SubprocessRunner()

    def list_launchable_apps(
        self,
        device_id: str,
        timeout_s: float = 5.0,
    ) -> DriverAppCatalog:
        return read_uiautomator2_launchable_apps(
            device_id=device_id,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
        )

    def open_app(
        self,
        *,
        device_id: str,
        package: str,
        activity: str | None = None,
        timeout_s: float = 10.0,
    ) -> DriverAppOpen:
        return open_uiautomator2_app(
            device_id=device_id,
            package=package,
            activity=activity,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
        )


def read_uiautomator2_launchable_apps(
    *,
    device_id: str,
    timeout_s: float = 5.0,
    process_runner: ProcessRunner | None = None,
) -> DriverAppCatalog:
    started = perf_counter()
    serial = normalize_serial(device_id)
    runner = process_runner or SubprocessRunner()
    if serial is None:
        return DriverAppCatalog.failure(
            backend="uiautomator2",
            code="device_offline",
            detail="Device serial is required and must be a valid ADB serial.",
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )
    args = [
        "adb",
        "-s",
        serial,
        "shell",
        "cmd",
        "package",
        "query-activities",
        "--brief",
        "-a",
        "android.intent.action.MAIN",
        "-c",
        "android.intent.category.LAUNCHER",
    ]
    try:
        result = runner.run(args, timeout_s=timeout_s)
    except ProcessTimeoutError as exc:
        return _catalog_failure(
            code="driver_timeout",
            detail=str(exc) or "Launchable app listing timed out.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": timeout_s},
        )
    except OSError as exc:
        return _catalog_failure(
            code="driver_unavailable",
            detail=str(exc) or "ADB app lifecycle driver is unavailable.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": timeout_s},
        )
    if result.returncode != 0:
        return _catalog_failure(
            code="app_unavailable",
            detail="Unable to list launchable apps.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": timeout_s, "returncode": result.returncode},
        )
    apps = parse_launchable_activities(result.stdout)
    return DriverAppCatalog.success(
        device_id=serial,
        backend="uiautomator2",
        elapsed_ms=_elapsed_ms(started),
        apps=apps,
        metadata={"timeout_s": timeout_s, "count": len(apps)},
    )


def open_uiautomator2_app(
    *,
    device_id: str,
    package: str,
    activity: str | None = None,
    timeout_s: float = 10.0,
    process_runner: ProcessRunner | None = None,
) -> DriverAppOpen:
    started = perf_counter()
    serial = normalize_serial(device_id)
    package_name = normalize_package(package)
    runner = process_runner or SubprocessRunner()
    if serial is None:
        return _open_failure(
            code="device_offline",
            detail="Device serial is required and must be a valid ADB serial.",
            elapsed_ms=_elapsed_ms(started),
        )
    if package_name is None:
        return _open_failure(
            code="app_unavailable",
            detail="Package is required and must be a valid Android package name.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
        )

    args = _open_args(serial=serial, package=package_name, activity=activity)
    try:
        result = runner.run(args, timeout_s=timeout_s)
    except ProcessTimeoutError as exc:
        return _open_failure(
            code="driver_timeout",
            detail=str(exc) or f"Opening {package_name} timed out.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            attempted=True,
            metadata=_open_metadata(
                package=package_name,
                activity=activity,
                timeout_s=timeout_s,
                touch_may_have_occurred=True,
            ),
        )
    except OSError as exc:
        return _open_failure(
            code="driver_unavailable",
            detail=str(exc) or "ADB app lifecycle driver is unavailable.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=_open_metadata(
                package=package_name,
                activity=activity,
                timeout_s=timeout_s,
            ),
        )

    metadata = _open_metadata(
        package=package_name,
        activity=activity,
        timeout_s=timeout_s,
        returncode=result.returncode,
    )
    if result.returncode != 0:
        return _open_failure(
            code="app_unavailable",
            detail=f"Unable to open launchable app {package_name}.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            attempted=True,
            metadata={**metadata, "touch_may_have_occurred": True},
        )
    return DriverAppOpen(
        ok=True,
        status="completed",
        device_id=serial,
        backend="uiautomator2",
        operation="app_open",
        elapsed_ms=_elapsed_ms(started),
        attempted=True,
        confirmed=True,
        checked_at=_utc_now(),
        metadata=metadata,
    )


def parse_launchable_activities(output: str) -> tuple[DriverAppEntry, ...]:
    entries: list[DriverAppEntry] = []
    seen: set[tuple[str, str | None]] = set()
    for line in output.splitlines():
        match = _COMPONENT_RE.match(line)
        if match is None:
            continue
        package = normalize_package(match.group(1))
        if package is None:
            continue
        activity = match.group(2).strip() or None
        key = (package, activity)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            DriverAppEntry(
                package=package,
                activity=activity,
            )
        )
    return tuple(entries)


def _open_args(
    *,
    serial: str,
    package: str,
    activity: str | None,
) -> list[str]:
    if activity is not None:
        return [
            "adb",
            "-s",
            serial,
            "shell",
            "am",
            "start",
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.LAUNCHER",
            "-n",
            f"{package}/{activity}",
        ]
    return [
        "adb",
        "-s",
        serial,
        "shell",
        "monkey",
        "-p",
        package,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
    ]


def _catalog_failure(
    *,
    code: str,
    detail: str,
    elapsed_ms: float,
    device_id: str | None = None,
    status: str = "unhealthy",
    metadata: Mapping[str, object] | None = None,
) -> DriverAppCatalog:
    return DriverAppCatalog.failure(
        backend="uiautomator2",
        code=code,
        detail=detail,
        device_id=device_id,
        elapsed_ms=elapsed_ms,
        status=status,
        metadata=metadata,
    )


def _open_failure(
    *,
    code: str,
    detail: str,
    elapsed_ms: float,
    device_id: str | None = None,
    metadata: Mapping[str, object] | None = None,
    attempted: bool = False,
) -> DriverAppOpen:
    return DriverAppOpen(
        ok=False,
        status="failed" if attempted else "blocked",
        device_id=device_id,
        backend="uiautomator2",
        operation="app_open",
        elapsed_ms=elapsed_ms,
        attempted=attempted,
        confirmed=False,
        checked_at=_utc_now(),
        metadata=metadata or {},
        error=DriverError(code=code, detail=detail),
    )


def _open_metadata(
    *,
    package: str,
    activity: str | None,
    timeout_s: float,
    returncode: int | None = None,
    touch_may_have_occurred: bool | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "package": package,
        "timeout_s": timeout_s,
    }
    if activity is not None:
        metadata["activity"] = activity
    if returncode is not None:
        metadata["returncode"] = returncode
    if touch_may_have_occurred is not None:
        metadata["touch_may_have_occurred"] = touch_may_have_occurred
    return metadata


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
