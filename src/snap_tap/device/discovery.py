from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from snap_tap.device.identity import DeviceInfo, normalize_serial


class DeviceDiscovery(Protocol):
    def list_devices(self) -> Sequence[DeviceInfo]: ...


class DeviceDiscoveryError(RuntimeError):
    pass


class AdbDeviceDiscovery:
    def list_devices(self) -> Sequence[DeviceInfo]:
        try:
            import adbutils  # type: ignore[import-untyped]
        except Exception as exc:
            raise DeviceDiscoveryError("ADB discovery dependency is unavailable.") from exc

        devices: list[DeviceInfo] = []
        try:
            adb_devices = adbutils.adb.device_list()
        except Exception as exc:
            raise DeviceDiscoveryError("ADB device discovery failed.") from exc
        for device in adb_devices:
            device_info = _device_info_from_adb(device)
            if device_info is not None:
                devices.append(device_info)
        return devices


def _device_info_from_adb(device: object) -> DeviceInfo | None:
    serial = normalize_serial(getattr(device, "serial", None))
    if serial is None:
        return None
    return DeviceInfo(
        serial=serial,
        state=_read_state(device),
        product=_safe_getprop(device, "ro.product.name"),
        model=_safe_getprop(device, "ro.product.model"),
        device=_safe_getprop(device, "ro.product.device"),
    )


def _read_state(device: object) -> str:
    get_state = getattr(device, "get_state", None)
    if not callable(get_state):
        return "unknown"
    try:
        return str(get_state())
    except Exception:
        return "unknown"


def _safe_getprop(device: object, prop: str) -> str | None:
    getprop = getattr(device, "getprop", None)
    if not callable(getprop):
        return None
    try:
        value = getprop(prop)
    except Exception:
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None
