from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import re


_VALID_SERIAL_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    state: str = "unknown"
    product: str | None = None
    model: str | None = None
    device: str | None = None


@dataclass(frozen=True)
class DeviceSelection:
    ok: bool
    device: DeviceInfo | None
    error_code: str | None = None
    error_detail: str | None = None


def normalize_serial(serial: object | None) -> str | None:
    if not isinstance(serial, str):
        return None
    normalized = serial.strip()
    if not normalized:
        return None
    if _VALID_SERIAL_RE.fullmatch(normalized) is None:
        return None
    return normalized


def select_device(
    devices: Sequence[DeviceInfo],
    requested_serial: str | None,
) -> DeviceSelection:
    requested = normalize_serial(requested_serial)
    if requested_serial is not None and requested is None:
        return DeviceSelection(
            ok=False,
            device=None,
            error_code="device_offline",
            error_detail="Device serial is required and must be a valid ADB serial.",
        )

    if requested:
        for device in devices:
            device_serial = normalize_serial(device.serial)
            if device_serial == requested:
                if device.state != "device":
                    return DeviceSelection(
                        ok=False,
                        device=device,
                        error_code="device_offline",
                        error_detail=(
                            f"Device {requested} is present but state is "
                            f"{device.state!r}."
                        ),
                    )
                return DeviceSelection(ok=True, device=device)
        return DeviceSelection(
            ok=False,
            device=None,
            error_code="device_offline",
            error_detail=f"Device {requested} is not visible to ADB.",
        )

    online_devices = [
        device
        for device in devices
        if device.state == "device" and normalize_serial(device.serial) is not None
    ]
    if not online_devices:
        return DeviceSelection(
            ok=False,
            device=None,
            error_code="device_offline",
            error_detail="No online Android devices with valid serials are visible.",
        )
    if len(online_devices) > 1:
        serials = ", ".join(device.serial.strip() for device in online_devices)
        return DeviceSelection(
            ok=False,
            device=None,
            error_code="driver_conflict",
            error_detail=(
                "Multiple Android devices are online; pass an explicit serial. "
                f"Visible devices: {serials}."
            ),
        )
    return DeviceSelection(ok=True, device=online_devices[0])


__all__ = [
    "DeviceInfo",
    "DeviceSelection",
    "normalize_serial",
    "select_device",
]
