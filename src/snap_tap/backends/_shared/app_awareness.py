from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol

from snap_tap.backends._shared.errors import DriverError
from snap_tap.device.identity import DeviceInfo, select_device

_PACKAGE_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$"
)


@dataclass(frozen=True)
class DriverAppAwareness:
    ok: bool
    status: str
    device_id: str | None
    backend: str
    operation: str
    checked_at: str
    elapsed_ms: float
    metadata: Mapping[str, object] = field(default_factory=dict)
    error: DriverError | None = None

    @classmethod
    def success(
        cls,
        *,
        device_id: str,
        backend: str,
        operation: str,
        elapsed_ms: float,
        metadata: Mapping[str, object],
    ) -> DriverAppAwareness:
        return cls(
            ok=True,
            status="completed",
            device_id=device_id,
            backend=backend,
            operation=operation,
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            metadata=metadata,
        )

    @classmethod
    def failure(
        cls,
        *,
        backend: str,
        operation: str,
        code: str,
        detail: str,
        elapsed_ms: float,
        device_id: str | None = None,
        status: str = "unhealthy",
        metadata: Mapping[str, object] | None = None,
    ) -> DriverAppAwareness:
        return cls(
            ok=False,
            status=status,
            device_id=device_id,
            backend=backend,
            operation=operation,
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            metadata=metadata or {},
            error=DriverError(code=code, detail=detail),
        )


class DriverAppAwarenessReader(Protocol):
    backend_name: str

    def app_current(
        self,
        device_id: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness: ...

    def package_info(
        self,
        device_id: str,
        package: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness: ...


def read_device_app_current(
    *,
    reader: DriverAppAwarenessReader,
    devices: Sequence[DeviceInfo],
    requested_serial: str | None,
    timeout_s: float = 5.0,
) -> DriverAppAwareness:
    return _run_selected(
        reader=reader,
        devices=devices,
        requested_serial=requested_serial,
        operation="app_current",
        package=None,
        timeout_s=timeout_s,
    )


def read_device_package_info(
    *,
    reader: DriverAppAwarenessReader,
    devices: Sequence[DeviceInfo],
    requested_serial: str | None,
    package: str,
    timeout_s: float = 5.0,
) -> DriverAppAwareness:
    return _run_selected(
        reader=reader,
        devices=devices,
        requested_serial=requested_serial,
        operation="package_info",
        package=package,
        timeout_s=timeout_s,
    )


def normalize_package(package: object | None) -> str | None:
    if not isinstance(package, str):
        return None
    normalized = package.strip()
    if not normalized:
        return None
    if _PACKAGE_RE.fullmatch(normalized) is None:
        return None
    return normalized


def _run_selected(
    *,
    reader: DriverAppAwarenessReader,
    devices: Sequence[DeviceInfo],
    requested_serial: str | None,
    operation: str,
    package: str | None,
    timeout_s: float,
) -> DriverAppAwareness:
    started = perf_counter()
    package_name = normalize_package(package) if operation == "package_info" else None
    if operation == "package_info" and package_name is None:
        return _app_failure(
            backend=reader.backend_name,
            operation=operation,
            code="app_unavailable",
            detail="Package is required and must be a valid Android package name.",
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )

    selection = select_device(devices, requested_serial)
    if not selection.ok:
        return _app_failure(
            backend=reader.backend_name,
            operation=operation,
            code=selection.error_code or "driver_unavailable",
            detail=selection.error_detail or "Device selection failed.",
            device_id=selection.device.serial if selection.device else requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )
    if selection.device is None:
        return _app_failure(
            backend=reader.backend_name,
            operation=operation,
            code="driver_unavailable",
            detail="Device selection succeeded without a device.",
            device_id=requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )
    if operation == "app_current":
        return reader.app_current(selection.device.serial, timeout_s=timeout_s)
    if package_name is None:
        return _app_failure(
            backend=reader.backend_name,
            operation=operation,
            code="app_unavailable",
            detail="Package is required and must be a valid Android package name.",
            device_id=selection.device.serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )
    return reader.package_info(
        selection.device.serial,
        package_name,
        timeout_s=timeout_s,
    )


def _app_failure(
    *,
    backend: str,
    operation: str,
    code: str,
    detail: str,
    elapsed_ms: float,
    device_id: str | None = None,
    status: str = "unhealthy",
    metadata: Mapping[str, object] | None = None,
) -> DriverAppAwareness:
    return DriverAppAwareness.failure(
        backend=backend,
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


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
