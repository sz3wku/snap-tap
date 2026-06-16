from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol

from snap_tap.device.identity import DeviceInfo, select_device
from snap_tap.backends._shared.errors import DriverError


@dataclass(frozen=True)
class DriverHealth:
    ok: bool
    status: str
    device_id: str | None
    backend: str
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
        elapsed_ms: float,
        metadata: Mapping[str, object] | None = None,
    ) -> DriverHealth:
        return cls(
            ok=True,
            status="healthy",
            device_id=device_id,
            backend=backend,
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            metadata=metadata or {},
        )

    @classmethod
    def failure(
        cls,
        *,
        backend: str,
        code: str,
        detail: str,
        elapsed_ms: float,
        device_id: str | None = None,
        status: str = "unhealthy",
        metadata: Mapping[str, object] | None = None,
    ) -> DriverHealth:
        return cls(
            ok=False,
            status=status,
            device_id=device_id,
            backend=backend,
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            metadata=metadata or {},
            error=DriverError(code=code, detail=detail),
        )


class DriverBackend(Protocol):
    backend_name: str

    def health(self, device_id: str, timeout_s: float = 5.0) -> DriverHealth: ...


def check_device_health(
    *,
    backend: DriverBackend,
    devices: Sequence[DeviceInfo],
    requested_serial: str | None,
    timeout_s: float = 5.0,
) -> DriverHealth:
    started = perf_counter()
    selection = select_device(devices, requested_serial)
    if not selection.ok:
        return DriverHealth.failure(
            backend=backend.backend_name,
            code=selection.error_code or "driver_unavailable",
            detail=selection.error_detail or "Device selection failed.",
            device_id=selection.device.serial if selection.device else requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )
    if selection.device is None:
        return DriverHealth.failure(
            backend=backend.backend_name,
            code="driver_unavailable",
            detail="Device selection succeeded without a device.",
            device_id=requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )
    return backend.health(selection.device.serial, timeout_s=timeout_s)


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
