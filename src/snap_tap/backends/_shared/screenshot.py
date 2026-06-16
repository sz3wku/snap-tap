from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol

from snap_tap.backends._shared.errors import DriverError
from snap_tap.device.identity import DeviceInfo, select_device


@dataclass(frozen=True)
class DriverScreenshot:
    ok: bool
    status: str
    device_id: str | None
    backend: str
    operation: str
    checked_at: str
    elapsed_ms: float
    path: str | None = None
    image_bytes: bytes | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    error: DriverError | None = None

    @classmethod
    def success(
        cls,
        *,
        device_id: str,
        backend: str,
        elapsed_ms: float,
        image_bytes: bytes,
        metadata: Mapping[str, object] | None = None,
    ) -> DriverScreenshot:
        return cls(
            ok=True,
            status="completed",
            device_id=device_id,
            backend=backend,
            operation="screenshot",
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            image_bytes=image_bytes,
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
        path: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> DriverScreenshot:
        return cls(
            ok=False,
            status=status,
            device_id=device_id,
            backend=backend,
            operation="screenshot",
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            path=path,
            metadata=metadata or {},
            error=DriverError(code=code, detail=detail),
        )

    def with_path(self, path: str) -> DriverScreenshot:
        return replace(self, path=path)


class DriverScreenshotCapturer(Protocol):
    backend_name: str

    def capture(
        self,
        device_id: str,
        timeout_s: float = 10.0,
    ) -> DriverScreenshot: ...


def capture_device_screenshot(
    *,
    capturer: DriverScreenshotCapturer,
    devices: Sequence[DeviceInfo],
    requested_serial: str | None,
    timeout_s: float = 10.0,
) -> DriverScreenshot:
    started = perf_counter()
    selection = select_device(devices, requested_serial)
    if not selection.ok:
        return DriverScreenshot.failure(
            backend=capturer.backend_name,
            code=selection.error_code or "driver_unavailable",
            detail=selection.error_detail or "Device selection failed.",
            device_id=selection.device.serial if selection.device else requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
            metadata={"timeout_s": timeout_s},
        )
    if selection.device is None:
        return DriverScreenshot.failure(
            backend=capturer.backend_name,
            code="driver_unavailable",
            detail="Device selection succeeded without a device.",
            device_id=requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
            metadata={"timeout_s": timeout_s},
        )
    return capturer.capture(selection.device.serial, timeout_s=timeout_s)


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
