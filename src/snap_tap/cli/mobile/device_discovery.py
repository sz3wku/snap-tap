from __future__ import annotations

from dataclasses import dataclass

from snap_tap.cli.output import error_to_dict
from snap_tap.device.discovery import DeviceDiscovery
from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.contracts import (
    DriverError,
    DriverHealth,
    DriverLifecycleResult,
    DriverXmlDump,
)


DISCOVERY_FAILURE_DETAIL = "Android device discovery failed before command execution."


@dataclass(frozen=True)
class DeviceDiscoverySnapshot:
    devices: list[DeviceInfo]
    error: DriverError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def read_visible_devices(discovery: DeviceDiscovery) -> DeviceDiscoverySnapshot:
    try:
        return DeviceDiscoverySnapshot(devices=list(discovery.list_devices()))
    except Exception:
        return DeviceDiscoverySnapshot(
            devices=[],
            error=DriverError(
                code="driver_unavailable",
                detail=DISCOVERY_FAILURE_DETAIL,
            ),
        )


def devices_failure_payload(error: DriverError) -> dict[str, object]:
    return {
        "ok": False,
        "count": 0,
        "devices": [],
        "error": error_to_dict(error),
    }


def discovery_health_failure(
    error: DriverError,
    *,
    backend: str,
    device_id: str | None,
) -> DriverHealth:
    return blocked_health(
        backend=backend,
        code=error.code,
        detail=error.detail,
        device_id=device_id,
    )


def blocked_health(
    *,
    backend: str,
    code: str,
    detail: str,
    device_id: str | None,
) -> DriverHealth:
    return DriverHealth.failure(
        backend=backend,
        code=code,
        detail=detail,
        device_id=device_id,
        elapsed_ms=0.0,
        status="blocked",
    )


def discovery_lifecycle_failure(
    error: DriverError,
    *,
    backend: str,
    operation: str,
    device_id: str | None,
) -> DriverLifecycleResult:
    return DriverLifecycleResult.failure(
        backend=backend,
        operation=operation,
        code=error.code,
        detail=error.detail,
        device_id=device_id,
        elapsed_ms=0.0,
        status="blocked",
    )


def discovery_xml_failure(
    error: DriverError,
    *,
    backend: str,
    device_id: str | None,
) -> DriverXmlDump:
    return DriverXmlDump.failure(
        backend=backend,
        code=error.code,
        detail=error.detail,
        device_id=device_id,
        elapsed_ms=0.0,
        status="blocked",
    )
