from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter
import sys

from snap_tap.device.identity import DeviceInfo, normalize_serial, select_device
from snap_tap.backends.contracts import DriverXmlDump, DriverXmlDumper
from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessRunner,
    ProcessTimeoutError,
    SubprocessRunner,
)
from snap_tap.backends.android.uiautomator2.probe_payload import (
    parse_probe_payload,
    probe_error_code,
    probe_error_detail,
)
from snap_tap.backends.android.uiautomator2.recovery import retry_once_after_recovery


class Uiautomator2XmlDumper:
    backend_name = "uiautomator2"

    def __init__(
        self,
        *,
        process_runner: ProcessRunner | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._process_runner = process_runner or SubprocessRunner()
        self._python_executable = python_executable or sys.executable

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        return dump_uiautomator2_xml(
            device_id=device_id,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
            python_executable=self._python_executable,
        )


def dump_device_xml(
    *,
    dumper: DriverXmlDumper,
    devices: Sequence[DeviceInfo],
    requested_serial: str | None,
    timeout_s: float = 10.0,
) -> DriverXmlDump:
    started = perf_counter()
    selection = select_device(devices, requested_serial)
    if not selection.ok:
        return DriverXmlDump.failure(
            backend=dumper.backend_name,
            code=selection.error_code or "driver_unavailable",
            detail=selection.error_detail or "Device selection failed.",
            device_id=selection.device.serial if selection.device else requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )
    if selection.device is None:
        return DriverXmlDump.failure(
            backend=dumper.backend_name,
            code="driver_unavailable",
            detail="Device selection succeeded without a device.",
            device_id=requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )
    return dumper.dump_xml(selection.device.serial, timeout_s=timeout_s)


def dump_uiautomator2_xml(
    *,
    device_id: str,
    timeout_s: float = 10.0,
    process_runner: ProcessRunner | None = None,
    python_executable: str | None = None,
) -> DriverXmlDump:
    started = perf_counter()
    serial = normalize_serial(device_id)
    runner = process_runner or SubprocessRunner()
    executable = python_executable or sys.executable

    if serial is None:
        return DriverXmlDump.failure(
            backend="uiautomator2",
            code="device_offline",
            detail="Device serial is required and must be a valid ADB serial.",
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
        )

    result = _dump_uiautomator2_xml_once(
        serial=serial,
        timeout_s=timeout_s,
        runner=runner,
        executable=executable,
        started=started,
    )
    return retry_once_after_recovery(
        result,
        device_id=serial,
        operation="dump_xml",
        process_runner=runner,
        python_executable=executable,
        retry=lambda: _dump_uiautomator2_xml_once(
            serial=serial,
            timeout_s=timeout_s,
            runner=runner,
            executable=executable,
            started=started,
        ),
    )


def _dump_uiautomator2_xml_once(
    *,
    serial: str,
    timeout_s: float,
    runner: ProcessRunner,
    executable: str,
    started: float,
) -> DriverXmlDump:
    args = [
        executable,
        "-m",
        "snap_tap.backends.android.uiautomator2.probes",
        "dump_xml",
        "--device",
        serial,
    ]
    try:
        result = runner.run(args, timeout_s=timeout_s)
    except ProcessTimeoutError as exc:
        return DriverXmlDump.failure(
            backend="uiautomator2",
            code="driver_timeout",
            detail=str(exc) or "uiautomator2 dump_xml timed out.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": str(timeout_s)},
        )
    except OSError as exc:
        return DriverXmlDump.failure(
            backend="uiautomator2",
            code="driver_unavailable",
            detail=str(exc) or "uiautomator2 dump_xml driver is unavailable.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": str(timeout_s)},
        )

    payload = parse_probe_payload(result.stdout)
    metadata = _probe_metadata(payload, timeout_s=timeout_s)
    if result.returncode != 0 or payload.get("ok") is not True:
        return DriverXmlDump.failure(
            backend="uiautomator2",
            code=_probe_error_code(payload),
            detail=_probe_error_detail(payload),
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
        )

    xml = payload.get("xml")
    if not isinstance(xml, str) or not xml.strip():
        return DriverXmlDump.failure(
            backend="uiautomator2",
            code="dump_failed",
            detail="uiautomator2 dump_xml probe returned empty XML.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
        )

    metadata = {**_xml_metadata(xml), **metadata}
    return DriverXmlDump.success(
        device_id=serial,
        backend="uiautomator2",
        elapsed_ms=_elapsed_ms(started),
        xml=xml,
        metadata=metadata,
    )


def _probe_metadata(
    payload: Mapping[str, object],
    *,
    timeout_s: float,
) -> dict[str, str]:
    metadata = {"timeout_s": str(timeout_s)}
    raw_metadata = payload.get("metadata")
    if not isinstance(raw_metadata, Mapping):
        return metadata
    for key, value in raw_metadata.items():
        metadata[str(key)] = str(value)
    return metadata


def _probe_error_code(payload: Mapping[str, object]) -> str:
    return probe_error_code(payload, default_code="dump_failed")


def _probe_error_detail(payload: Mapping[str, object]) -> str:
    return probe_error_detail(payload, operation="dump_xml")


def _xml_metadata(xml: str) -> dict[str, str]:
    return {
        "byte_length": str(len(xml.encode("utf-8"))),
        "node_count": str(xml.count("<node")),
    }


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
