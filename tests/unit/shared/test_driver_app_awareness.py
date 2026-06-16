from __future__ import annotations

from snap_tap.backends.contracts import (
    DriverAppAwareness,
    read_device_app_current,
    read_device_package_info,
)
from snap_tap.device.identity import DeviceInfo


class FakeAppReader:
    backend_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, float]] = []

    def app_current(
        self,
        device_id: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness:
        self.calls.append(("app_current", device_id, timeout_s))
        return DriverAppAwareness.success(
            device_id=device_id,
            backend=self.backend_name,
            operation="app_current",
            elapsed_ms=1.0,
            metadata={"package": "com.example.app", "activity": ".Main"},
        )

    def package_info(
        self,
        device_id: str,
        package: str,
        timeout_s: float = 5.0,
    ) -> DriverAppAwareness:
        self.calls.append((device_id, package, timeout_s))
        return DriverAppAwareness.success(
            device_id=device_id,
            backend=self.backend_name,
            operation="package_info",
            elapsed_ms=1.0,
            metadata={"package": package, "version_name": "1.2.3"},
        )


def test_read_device_app_current_auto_selects_single_online_device() -> None:
    reader = FakeAppReader()

    result = read_device_app_current(
        reader=reader,
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial=None,
        timeout_s=3.0,
    )

    assert result.ok is True
    assert result.operation == "app_current"
    assert reader.calls == [("app_current", "RFCN4010FCK", 3.0)]


def test_read_device_app_current_blocks_ambiguous_multi_device_selection() -> None:
    reader = FakeAppReader()

    result = read_device_app_current(
        reader=reader,
        devices=[
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ],
        requested_serial=None,
    )

    assert result.ok is False
    assert result.status == "blocked"
    assert result.error is not None
    assert result.error.code == "driver_conflict"
    assert reader.calls == []


def test_read_device_package_info_rejects_malformed_package_before_reader() -> None:
    reader = FakeAppReader()

    result = read_device_package_info(
        reader=reader,
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="RFCN4010FCK",
        package="bad package",
    )

    assert result.ok is False
    assert result.status == "blocked"
    assert result.error is not None
    assert result.error.code == "app_unavailable"
    assert reader.calls == []


def test_read_device_package_info_accepts_single_segment_package_name() -> None:
    reader = FakeAppReader()

    result = read_device_package_info(
        reader=reader,
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="RFCN4010FCK",
        package="android",
        timeout_s=2.0,
    )

    assert result.ok is True
    assert reader.calls == [("RFCN4010FCK", "android", 2.0)]
