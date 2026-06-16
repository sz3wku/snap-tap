from __future__ import annotations

from snap_tap.cli.mobile.device_discovery import read_command_devices
from snap_tap.device.identity import DeviceInfo


class FakeDiscovery:
    def __init__(self) -> None:
        self.calls = 0

    def list_devices(self) -> list[DeviceInfo]:
        self.calls += 1
        return [DeviceInfo(serial="RFCN4010FCK", state="device")]


def test_read_command_devices_uses_minimal_explicit_serial_without_discovery() -> None:
    discovery = FakeDiscovery()

    snapshot = read_command_devices(
        discovery,
        requested_serial=" RFCN4010FCK ",
    )

    assert snapshot.ok is True
    assert snapshot.devices == [DeviceInfo(serial="RFCN4010FCK", state="device")]
    assert discovery.calls == 0


def test_read_command_devices_rejects_malformed_explicit_serial() -> None:
    discovery = FakeDiscovery()

    snapshot = read_command_devices(
        discovery,
        requested_serial="bad serial",
    )

    assert snapshot.ok is False
    assert snapshot.error is not None
    assert snapshot.error.code == "device_offline"
    assert discovery.calls == 0


def test_read_command_devices_without_serial_keeps_full_discovery() -> None:
    discovery = FakeDiscovery()

    snapshot = read_command_devices(discovery, requested_serial=None)

    assert snapshot.ok is True
    assert snapshot.devices == [DeviceInfo(serial="RFCN4010FCK", state="device")]
    assert discovery.calls == 1
