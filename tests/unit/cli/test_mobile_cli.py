from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import typer
from typer.testing import CliRunner

from snap_tap.backends.contracts import (
    DriverHealth,
    DriverLifecycleResult,
    DriverXmlDump,
)
from snap_tap.cli.mobile.app import MobileDependencies, build_mobile_app
from snap_tap.device.identity import DeviceInfo


class FakeDiscovery:
    def __init__(self, devices: Sequence[DeviceInfo]) -> None:
        self._devices = list(devices)

    def list_devices(self) -> Sequence[DeviceInfo]:
        return list(self._devices)


class FakeBackend:
    backend_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []

    def health(self, device_id: str, timeout_s: float = 5.0) -> DriverHealth:
        self.calls.append((device_id, timeout_s))
        return DriverHealth.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            metadata={"timeout_s": str(timeout_s)},
        )


class FakeLifecycleRunner:
    backend_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []

    def run(
        self,
        *,
        operation: str,
        device_id: str,
        timeout_s: float = 60.0,
    ) -> DriverLifecycleResult:
        self.calls.append((operation, device_id, timeout_s))
        return DriverLifecycleResult.success(
            device_id=device_id,
            backend=self.backend_name,
            operation=operation,
            elapsed_ms=1.0,
            metadata={"timeout_s": str(timeout_s)},
        )


class FakeXmlDumper:
    backend_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        self.calls.append((device_id, timeout_s))
        return DriverXmlDump.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            xml="<hierarchy><node /></hierarchy>",
            metadata={"timeout_s": str(timeout_s)},
        )


def test_mobile_devices_outputs_visible_devices_as_json() -> None:
    app, _, _, _ = _build_app(
        [
            DeviceInfo(
                serial="RFCN4010FCK",
                state="device",
                product="x1sxeea",
                model="SM_G981B",
                device="x1s",
            )
        ]
    )

    result = CliRunner().invoke(app, ["devices", "--json"])

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["devices"][0]["serial"] == "RFCN4010FCK"
    assert payload["devices"][0]["model"] == "SM_G981B"


def test_mobile_devices_default_outputs_human_table() -> None:
    app, _, _, _ = _build_app(
        [
            DeviceInfo(
                serial="RFCN4010FCK",
                state="device",
                product="x1sxeea",
                model="SM_G981B",
                device="x1s",
            )
        ]
    )

    result = CliRunner().invoke(app, ["devices"])

    assert result.exit_code == 0
    assert "SERIAL" in result.stdout
    assert "RFCN4010FCK" in result.stdout
    assert "SM_G981B" in result.stdout
    assert not result.stdout.lstrip().startswith("{")


def test_mobile_devices_default_never_truncates_serial_column() -> None:
    long_serial = "00008130-000935222230001C"
    app, _, _, _ = _build_app(
        [
            DeviceInfo(
                serial=long_serial,
                state="device",
                product="iphone-product-that-may-be-long",
                model="iPhone 15 Pro Max With Long Marketing Name",
                device="iphone",
            )
        ]
    )

    result = CliRunner().invoke(app, ["devices"])

    assert result.exit_code == 0
    assert long_serial in result.stdout
    assert long_serial[:18] + "  device" not in result.stdout


def test_mobile_status_blocks_ambiguous_multi_device_selection() -> None:
    app, backend, _, _ = _build_app(
        [
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ]
    )

    result = CliRunner().invoke(app, ["status", "--json"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "driver_conflict"
    assert backend.calls == []


def test_mobile_status_all_checks_each_visible_device() -> None:
    app, backend, _, _ = _build_app(
        [
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ]
    )

    result = CliRunner().invoke(
        app,
        ["status", "--all", "--timeout-s", "2", "--json"],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert [item["device_id"] for item in payload["results"]] == [
        "RFCN4010FCK",
        "R58R502HMSJ",
    ]
    assert backend.calls == [("RFCN4010FCK", 2.0), ("R58R502HMSJ", 2.0)]


def test_mobile_status_accepts_positional_serial() -> None:
    app, backend, _, _ = _build_app(
        [
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ]
    )

    result = CliRunner().invoke(
        app,
        ["status", "RFCN4010FCK", "--timeout-s", "2", "--json"],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["device_id"] == "RFCN4010FCK"
    assert backend.calls == [("RFCN4010FCK", 2.0)]


def test_mobile_status_default_outputs_human_line() -> None:
    app, backend, _, _ = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(app, ["status", "RFCN4010FCK", "--timeout-s", "2"])

    assert result.exit_code == 0
    assert "RFCN4010FCK" in result.stdout
    assert "healthy" in result.stdout
    assert "fake" in result.stdout
    assert not result.stdout.lstrip().startswith("{")
    assert backend.calls == [("RFCN4010FCK", 2.0)]


def test_mobile_status_all_default_outputs_human_table() -> None:
    app, backend, _, _ = _build_app(
        [
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ]
    )

    result = CliRunner().invoke(app, ["status", "--all", "--timeout-s", "2"])

    assert result.exit_code == 0
    assert "SERIAL" in result.stdout
    assert "STATUS" in result.stdout
    assert "RFCN4010FCK" in result.stdout
    assert "R58R502HMSJ" in result.stdout
    assert not result.stdout.lstrip().startswith("{")
    assert backend.calls == [("RFCN4010FCK", 2.0), ("R58R502HMSJ", 2.0)]


def test_mobile_status_all_default_never_truncates_serial_column() -> None:
    long_serial = "00008130-000935222230001C"
    app, backend, _, _ = _build_app([DeviceInfo(serial=long_serial, state="device")])

    result = CliRunner().invoke(app, ["status", "--all"])

    assert result.exit_code == 0
    assert long_serial in result.stdout
    assert long_serial[:18] + "  healthy" not in result.stdout
    assert backend.calls == [(long_serial, 5.0)]


def test_mobile_status_rejects_all_with_explicit_device() -> None:
    app, backend, _, _ = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(
        app,
        ["status", "--all", "--device", "RFCN4010FCK", "--json"],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "invalid_arguments"
    assert backend.calls == []


def test_mobile_status_rejects_positional_serial_with_device_option() -> None:
    app, backend, _, _ = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(
        app,
        ["status", "RFCN4010FCK", "--device", "RFCN4010FCK", "--json"],
    )

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "invalid_arguments"
    assert backend.calls == []


def test_mobile_status_all_blocks_when_no_devices_are_visible() -> None:
    app, backend, _, _ = _build_app([])

    result = CliRunner().invoke(app, ["status", "--all", "--json"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["count"] == 0
    assert payload["results"] == []
    assert backend.calls == []


def test_mobile_android_driver_init_requires_explicit_device() -> None:
    app, _, lifecycle, _ = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(app, ["android-driver-init"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "device_required"
    assert lifecycle.calls == []


def test_mobile_android_driver_init_rejects_malformed_serial_before_lifecycle_runner() -> None:
    app, _, lifecycle, _ = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(app, ["android-driver-init", "--device", "bad serial"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "device_offline"
    assert lifecycle.calls == []


def test_mobile_init_alias_still_runs_for_compatibility() -> None:
    app, _, lifecycle, _ = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(app, ["init", "RFCN4010FCK"])

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["result"]["operation"] == "init"
    assert lifecycle.calls == [("init", "RFCN4010FCK", 60.0)]


def test_mobile_doctor_runs_lifecycle_for_explicit_device() -> None:
    app, _, lifecycle, _ = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(
        app,
        ["doctor", "RFCN4010FCK", "--timeout-s", "3"],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "doctor"
    assert lifecycle.calls == [("doctor", "RFCN4010FCK", 3.0)]


def test_mobile_android_driver_purge_requires_explicit_device() -> None:
    app, _, lifecycle, _ = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(app, ["android-driver-purge"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["operation"] == "purge"
    assert payload["result"]["error"]["code"] == "device_required"
    assert "android-driver-purge" in payload["result"]["error"]["detail"]
    assert lifecycle.calls == []


def test_mobile_android_driver_purge_runs_lifecycle_for_explicit_device() -> None:
    app, _, lifecycle, _ = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(
        app,
        ["android-driver-purge", "RFCN4010FCK", "--timeout-s", "7"],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "purge"
    assert lifecycle.calls == [("purge", "RFCN4010FCK", 7.0)]


def test_mobile_android_driver_purge_rejects_malformed_serial() -> None:
    app, _, lifecycle, _ = _build_app([DeviceInfo(serial="RFCN4010FCK", state="device")])

    result = CliRunner().invoke(app, ["android-driver-purge", "--device", "bad serial"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["operation"] == "purge"
    assert payload["result"]["error"]["code"] == "device_offline"
    assert lifecycle.calls == []


def test_mobile_dump_xml_blocks_ambiguous_multi_device_selection() -> None:
    app, _, _, xml_dumper = _build_app(
        [
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ]
    )

    result = CliRunner().invoke(app, ["dump-xml"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "driver_conflict"
    assert xml_dumper.calls == []


def test_mobile_dump_xml_blocks_when_no_devices_are_visible() -> None:
    app, _, _, xml_dumper = _build_app([])

    result = CliRunner().invoke(app, ["dump-xml"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "device_offline"
    assert xml_dumper.calls == []


def test_mobile_dump_xml_rejects_malformed_serial_before_dumper() -> None:
    app, _, _, xml_dumper = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(app, ["dump-xml", "--device", "bad serial"])

    assert result.exit_code == 1
    payload = _json(result.stdout)
    assert payload["ok"] is False
    assert payload["result"]["error"]["code"] == "device_offline"
    assert xml_dumper.calls == []


def test_mobile_dump_xml_outputs_metadata_without_raw_xml() -> None:
    app, _, _, xml_dumper = _build_app(
        [DeviceInfo(serial="RFCN4010FCK", state="device")]
    )

    result = CliRunner().invoke(
        app,
        ["dump-xml", "RFCN4010FCK", "--timeout-s", "3"],
    )

    assert result.exit_code == 0
    payload = _json(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["operation"] == "dump_xml"
    assert "xml" not in payload["result"]
    assert "<hierarchy" not in result.stdout
    assert payload["result"]["metadata"]["timeout_s"] == "3.0"
    assert xml_dumper.calls == [("RFCN4010FCK", 3.0)]


def _build_app(
    devices: Sequence[DeviceInfo],
) -> tuple[typer.Typer, FakeBackend, FakeLifecycleRunner, FakeXmlDumper]:
    backend = FakeBackend()
    lifecycle = FakeLifecycleRunner()
    xml_dumper = FakeXmlDumper()
    app = build_mobile_app(
        MobileDependencies(
            discovery=FakeDiscovery(devices),
            backend=backend,
            lifecycle_runner=lifecycle,
            xml_dumper=xml_dumper,
        )
    )
    return app, backend, lifecycle, xml_dumper


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload
