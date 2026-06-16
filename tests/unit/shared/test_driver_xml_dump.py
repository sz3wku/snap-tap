from __future__ import annotations

from collections.abc import Sequence

from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessResult,
    ProcessRunner,
    ProcessTimeoutError,
)
from snap_tap.backends.contracts import DriverXmlDump
from snap_tap.backends.android.uiautomator2.xml_dump import (
    dump_device_xml,
    dump_uiautomator2_xml,
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


def test_dump_device_xml_blocks_ambiguous_multi_device_selection() -> None:
    dumper = FakeXmlDumper()

    result = dump_device_xml(
        dumper=dumper,
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
    assert dumper.calls == []


def test_dump_device_xml_calls_dumper_for_explicit_serial() -> None:
    dumper = FakeXmlDumper()

    result = dump_device_xml(
        dumper=dumper,
        devices=[
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ],
        requested_serial="RFCN4010FCK",
        timeout_s=3.0,
    )

    assert result.ok is True
    assert result.operation == "dump_xml"
    assert result.xml == "<hierarchy><node /></hierarchy>"
    assert dumper.calls == [("RFCN4010FCK", 3.0)]


def test_dump_uiautomator2_xml_rejects_malformed_serial_without_subprocess() -> None:
    runner = FakeProcessRunner()

    result = dump_uiautomator2_xml(
        device_id="bad serial",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.status == "blocked"
    assert result.error is not None
    assert result.error.code == "device_offline"
    assert runner.calls == []


def test_dump_uiautomator2_xml_runs_probe_as_argument_list() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=0,
            stdout='{"ok": true, "xml": "<hierarchy><node /></hierarchy>"}',
            stderr="",
        )
    )

    result = dump_uiautomator2_xml(
        device_id="RFCN4010FCK",
        timeout_s=3.0,
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is True
    assert result.xml == "<hierarchy><node /></hierarchy>"
    assert result.metadata["timeout_s"] == "3.0"
    assert result.metadata["byte_length"] == "31"
    assert result.metadata["node_count"] == "1"
    assert runner.calls == [
        (
            [
                ".venv",
                "-m",
                "snap_tap.backends.android.uiautomator2.probes",
                "dump_xml",
                "--device",
                "RFCN4010FCK",
            ],
            3.0,
        )
    ]


def test_dump_uiautomator2_xml_timeout_returns_structured_failure() -> None:
    runner = FakeProcessRunner(exc=ProcessTimeoutError("dump timed out"))

    result = dump_uiautomator2_xml(
        device_id="RFCN4010FCK",
        timeout_s=0.01,
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_timeout"
    assert result.metadata["timeout_s"] == "0.01"


def test_dump_uiautomator2_xml_process_error_returns_structured_failure() -> None:
    runner = FakeProcessRunner(exc=OSError("python missing"))

    result = dump_uiautomator2_xml(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_unavailable"
    assert "python missing" in result.error.detail


def test_dump_uiautomator2_xml_failed_probe_returns_structured_failure() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(
            returncode=1,
            stdout=(
                '{"ok": false, "error": {"code": "dump_failed", '
                '"detail": "RuntimeError: blocked"}}'
            ),
            stderr="",
        )
    )

    result = dump_uiautomator2_xml(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "dump_failed"
    assert "blocked" in result.error.detail


def test_dump_uiautomator2_xml_empty_payload_is_failure() -> None:
    runner = FakeProcessRunner(
        result=ProcessResult(returncode=0, stdout='{"ok": true}', stderr="")
    )

    result = dump_uiautomator2_xml(
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable=".venv",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "dump_failed"
