from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from snap_tap.backends.android.uiautomator2.backend import Uiautomator2Backend
from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessResult,
    ProcessRunner,
    ProcessTimeoutError,
)
from snap_tap.backends.contracts import DriverHealth, check_device_health
from snap_tap.device.discovery import _device_info_from_adb
from snap_tap.device.identity import DeviceInfo, normalize_serial, select_device


@dataclass
class FakeDevice:
    info: dict[str, object]


@dataclass
class FakeAdbDevice:
    serial: object

    def get_state(self) -> str:
        return "device"

    def getprop(self, prop: str) -> str | None:
        values = {
            "ro.product.name": "x1sxeea",
            "ro.product.model": "SM-G981B",
            "ro.product.device": "x1s",
        }
        return values.get(prop)


class FakeBackend:
    backend_name = "fake"

    def __init__(self, result: DriverHealth | None = None) -> None:
        self.calls: list[str] = []
        self._result = result

    def health(self, device_id: str, timeout_s: float = 5.0) -> DriverHealth:
        self.calls.append(device_id)
        if self._result is not None:
            return self._result
        return DriverHealth.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            metadata={"timeout_s": str(timeout_s)},
        )


class FakeProcessRunner(ProcessRunner):
    def __init__(
        self,
        result: ProcessResult | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.calls: list[tuple[list[str], float]] = []
        self._result = result or ProcessResult(returncode=0, stdout="", stderr="")
        self._exc = exc

    def run(self, args: Sequence[str], timeout_s: float) -> ProcessResult:
        self.calls.append((list(args), timeout_s))
        if self._exc is not None:
            raise self._exc
        return self._result


def test_select_device_requires_serial_when_multiple_devices_are_online() -> None:
    selection = select_device(
        [
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ],
        requested_serial=None,
    )

    assert selection.ok is False
    assert selection.error_code == "driver_conflict"
    assert "RFCN4010FCK" in (selection.error_detail or "")
    assert "R58R502HMSJ" in (selection.error_detail or "")


def test_select_device_accepts_explicit_online_serial() -> None:
    selection = select_device(
        [
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ],
        requested_serial="RFCN4010FCK",
    )

    assert selection.ok is True
    assert selection.device == DeviceInfo(serial="RFCN4010FCK", state="device")


def test_select_device_rejects_missing_serial() -> None:
    selection = select_device(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="missing",
    )

    assert selection.ok is False
    assert selection.error_code == "device_offline"


def test_select_device_rejects_blank_requested_serial() -> None:
    selection = select_device(
        [DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="  ",
    )

    assert selection.ok is False
    assert selection.error_code == "device_offline"
    assert "valid ADB serial" in (selection.error_detail or "")


def test_normalize_serial_rejects_malformed_values() -> None:
    assert normalize_serial(None) is None
    assert normalize_serial(123) is None
    assert normalize_serial("bad serial") is None
    assert normalize_serial("bad/serial") is None
    assert normalize_serial(" RFCN4010FCK ") == "RFCN4010FCK"
    assert normalize_serial("192.168.1.20:5555") == "192.168.1.20:5555"


def test_discovery_rejects_malformed_adb_serials() -> None:
    assert _device_info_from_adb(FakeAdbDevice(serial=None)) is None
    assert _device_info_from_adb(FakeAdbDevice(serial=123)) is None
    assert _device_info_from_adb(FakeAdbDevice(serial="bad serial")) is None


def test_discovery_preserves_valid_adb_serial_metadata() -> None:
    device = _device_info_from_adb(FakeAdbDevice(serial="RFCN4010FCK"))

    assert device == DeviceInfo(
        serial="RFCN4010FCK",
        state="device",
        product="x1sxeea",
        model="SM-G981B",
        device="x1s",
    )


def test_select_device_ignores_online_devices_with_blank_serials() -> None:
    selection = select_device(
        [DeviceInfo(serial=" ", state="device")],
        requested_serial=None,
    )

    assert selection.ok is False
    assert selection.error_code == "device_offline"


def test_check_device_health_blocks_ambiguous_multi_device_selection() -> None:
    backend = FakeBackend()

    health = check_device_health(
        backend=backend,
        devices=[
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ],
        requested_serial=None,
    )

    assert health.ok is False
    assert health.status == "blocked"
    assert health.error is not None
    assert health.error.code == "driver_conflict"
    assert backend.calls == []


def test_check_device_health_calls_backend_for_explicit_serial() -> None:
    backend = FakeBackend()

    health = check_device_health(
        backend=backend,
        devices=[
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ],
        requested_serial="RFCN4010FCK",
        timeout_s=3.0,
    )

    assert health.ok is True
    assert health.device_id == "RFCN4010FCK"
    assert health.backend == "fake"
    assert backend.calls == ["RFCN4010FCK"]


def test_uiautomator2_backend_localizes_successful_health_metadata() -> None:
    backend = Uiautomator2Backend(
        connector=lambda serial: FakeDevice(
            info={
                "brand": "samsung",
                "model": "SM_G981B",
                "sdkInt": 33,
                "screenOn": True,
                "ignored": "not exported",
            }
        )
    )

    health = backend.health("RFCN4010FCK", timeout_s=2.0)

    assert health.ok is True
    assert health.device_id == "RFCN4010FCK"
    assert health.backend == "uiautomator2"
    assert health.metadata["model"] == "SM_G981B"
    assert health.metadata["screen_on"] == "true"
    assert health.metadata["keyguard_locked"] == "unknown"
    assert health.metadata["keyguard_secure"] == "unknown"
    assert health.metadata["timeout_s"] == "2.0"
    assert "ignored" not in health.metadata


def test_uiautomator2_backend_returns_structured_failure() -> None:
    def fail(_: str) -> object:
        raise OSError("driver not available")

    health = Uiautomator2Backend(connector=fail).health("RFCN4010FCK")

    assert health.ok is False
    assert health.device_id == "RFCN4010FCK"
    assert health.error is not None
    assert health.error.code == "driver_unavailable"
    assert "driver not available" in health.error.detail


def test_uiautomator2_backend_rejects_blank_device_id_without_connecting() -> None:
    calls: list[str] = []

    def connect(serial: str) -> object:
        calls.append(serial)
        return FakeDevice(info={})

    health = Uiautomator2Backend(connector=connect).health(" ")

    assert health.ok is False
    assert health.status == "blocked"
    assert health.error is not None
    assert health.error.code == "device_offline"
    assert calls == []


def test_uiautomator2_backend_enforces_health_timeout() -> None:
    runner = FakeProcessRunner(exc=ProcessTimeoutError("probe timed out"))

    health = Uiautomator2Backend(
        process_runner=runner,
        python_executable=".venv",
    ).health(
        "RFCN4010FCK",
        timeout_s=0.01,
    )

    assert health.ok is False
    assert health.error is not None
    assert health.error.code == "driver_timeout"
    assert runner.calls == [
        (
            [
                ".venv",
                "-m",
                "snap_tap.backends.android.uiautomator2.probes",
                "health",
                "--device",
                "RFCN4010FCK",
            ],
            0.01,
        )
    ]


def test_uiautomator2_backend_reads_process_probe_payload() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=0,
            stdout='{"ok": true, "metadata": {"model": "SM_G981B"}}',
            stderr="",
        )
    )

    health = Uiautomator2Backend(
        process_runner=runner,
        python_executable=".venv",
    ).health("RFCN4010FCK", timeout_s=2.0)

    assert health.ok is True
    assert health.metadata["model"] == "SM_G981B"
    assert health.metadata["timeout_s"] == "2.0"
