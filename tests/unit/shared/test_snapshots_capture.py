from __future__ import annotations

from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.contracts import DriverScreenshot
from snap_tap.backends.contracts import DriverXmlDump
from snap_tap.snapshots import capture_raw_snapshot


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"
XML_TEXT = "<hierarchy><node /></hierarchy>"


class FakeXmlDumper:
    backend_name = "fake"

    def __init__(self, result: DriverXmlDump | None = None) -> None:
        self.calls: list[tuple[str, float]] = []
        self._result = result

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump:
        self.calls.append((device_id, timeout_s))
        if self._result is not None:
            return self._result
        return DriverXmlDump.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            xml=XML_TEXT,
            metadata={"timeout_s": str(timeout_s)},
        )


class FakeScreenshotCapturer:
    backend_name = "fake"

    def __init__(self, result: DriverScreenshot | None = None) -> None:
        self.calls: list[tuple[str, float]] = []
        self._result = result

    def capture(
        self,
        device_id: str,
        timeout_s: float = 10.0,
    ) -> DriverScreenshot:
        self.calls.append((device_id, timeout_s))
        if self._result is not None:
            return self._result
        return DriverScreenshot.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=2.0,
            image_bytes=PNG_BYTES,
            metadata={
                "format": "png",
                "width": 1080,
                "height": 2400,
                "byte_length": len(PNG_BYTES),
                "sha256": "abc123",
                "timeout_s": timeout_s,
            },
        )


def test_capture_raw_snapshot_composes_xml_and_screenshot() -> None:
    xml_dumper = FakeXmlDumper()
    capturer = FakeScreenshotCapturer()

    result = capture_raw_snapshot(
        xml_dumper=xml_dumper,
        screenshot_capturer=capturer,
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="RFCN4010FCK",
        timeout_s=3.0,
    )

    assert result.ok is True
    assert result.operation == "snapshot_capture"
    assert result.xml == XML_TEXT
    assert result.image_bytes == PNG_BYTES
    assert result.metadata["xml_elapsed_ms"] == 1.0
    assert result.metadata["screenshot_elapsed_ms"] == 2.0
    assert result.metadata["screenshot_width"] == 1080
    assert xml_dumper.calls == [("RFCN4010FCK", 3.0)]
    assert capturer.calls == [("RFCN4010FCK", 3.0)]


def test_capture_raw_snapshot_preserves_source_recovery_metadata() -> None:
    xml_dumper = FakeXmlDumper(
        DriverXmlDump.success(
            device_id="RFCN4010FCK",
            backend="fake",
            elapsed_ms=1.0,
            xml=XML_TEXT,
            metadata={
                "recovery_attempted": True,
                "recovery_ok": True,
                "recovery_operation": "init",
                "recovered_after_failure": "driver_unavailable",
                "recovery_elapsed_ms": 12.0,
                "attempt": 2,
            },
        )
    )

    result = capture_raw_snapshot(
        xml_dumper=xml_dumper,
        screenshot_capturer=FakeScreenshotCapturer(),
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="RFCN4010FCK",
    )

    assert result.ok is True
    assert result.metadata["xml_recovery"] == {
        "attempt": 2,
        "recovery_attempted": True,
        "recovery_ok": True,
        "recovery_operation": "init",
        "recovered_after_failure": "driver_unavailable",
        "recovery_elapsed_ms": 12.0,
    }


def test_capture_raw_snapshot_requires_explicit_device_before_backends() -> None:
    xml_dumper = FakeXmlDumper()
    capturer = FakeScreenshotCapturer()

    result = capture_raw_snapshot(
        xml_dumper=xml_dumper,
        screenshot_capturer=capturer,
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial=None,
    )

    assert result.ok is False
    assert result.status == "blocked"
    assert result.error is not None
    assert result.error.code == "device_required"
    assert xml_dumper.calls == []
    assert capturer.calls == []


def test_capture_raw_snapshot_blocks_missing_device_before_selection() -> None:
    xml_dumper = FakeXmlDumper()
    capturer = FakeScreenshotCapturer()

    result = capture_raw_snapshot(
        xml_dumper=xml_dumper,
        screenshot_capturer=capturer,
        devices=[
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ],
        requested_serial=None,
    )

    assert result.ok is False
    assert result.status == "blocked"
    assert result.error is not None
    assert result.error.code == "device_required"
    assert xml_dumper.calls == []
    assert capturer.calls == []


def test_capture_raw_snapshot_rejects_malformed_serial_before_backends() -> None:
    xml_dumper = FakeXmlDumper()
    capturer = FakeScreenshotCapturer()

    result = capture_raw_snapshot(
        xml_dumper=xml_dumper,
        screenshot_capturer=capturer,
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="bad serial",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "device_offline"
    assert xml_dumper.calls == []
    assert capturer.calls == []


def test_capture_raw_snapshot_xml_failure_blocks_screenshot() -> None:
    xml_dumper = FakeXmlDumper(
        DriverXmlDump.failure(
            backend="fake",
            code="dump_failed",
            detail="xml blocked",
            device_id="RFCN4010FCK",
            elapsed_ms=1.0,
        )
    )
    capturer = FakeScreenshotCapturer()

    result = capture_raw_snapshot(
        xml_dumper=xml_dumper,
        screenshot_capturer=capturer,
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="RFCN4010FCK",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "snapshot_dump_failed"
    assert result.metadata["stage"] == "xml"
    assert result.metadata["source_error_code"] == "dump_failed"
    assert capturer.calls == []


def test_capture_raw_snapshot_redacts_hostile_source_detail() -> None:
    xml_dumper = FakeXmlDumper(
        DriverXmlDump.failure(
            backend="fake",
            code="dump_failed",
            detail="<hierarchy><node text='secret' /></hierarchy>",
            device_id="RFCN4010FCK",
            elapsed_ms=1.0,
        )
    )

    result = capture_raw_snapshot(
        xml_dumper=xml_dumper,
        screenshot_capturer=FakeScreenshotCapturer(),
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="RFCN4010FCK",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.detail == "Snapshot XML capture failed."


def test_capture_raw_snapshot_screenshot_failure_maps_to_evidence_missing() -> None:
    capturer = FakeScreenshotCapturer(
        DriverScreenshot.failure(
            backend="fake",
            code="screenshot_failed",
            detail="screen blocked",
            device_id="RFCN4010FCK",
            elapsed_ms=1.0,
        )
    )

    result = capture_raw_snapshot(
        xml_dumper=FakeXmlDumper(),
        screenshot_capturer=capturer,
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="RFCN4010FCK",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "snapshot_evidence_missing"
    assert result.metadata["stage"] == "screenshot"
    assert result.metadata["source_error_code"] == "screenshot_failed"


def test_capture_raw_snapshot_keeps_xml_recovery_when_screenshot_fails() -> None:
    recovered_xml = DriverXmlDump.success(
        device_id="RFCN4010FCK",
        backend="fake",
        elapsed_ms=1.0,
        xml=XML_TEXT,
        metadata={
            "recovery_attempted": True,
            "recovery_ok": True,
            "recovery_operation": "init",
            "recovered_after_failure": "driver_unavailable",
            "recovery_elapsed_ms": 12.0,
            "attempt": 2,
        },
    )
    failed_screenshot = DriverScreenshot.failure(
        backend="fake",
        code="screenshot_failed",
        detail="blocked",
        device_id="RFCN4010FCK",
        elapsed_ms=2.0,
    )

    result = capture_raw_snapshot(
        xml_dumper=FakeXmlDumper(recovered_xml),
        screenshot_capturer=FakeScreenshotCapturer(failed_screenshot),
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="RFCN4010FCK",
    )

    assert result.ok is False
    assert result.metadata["xml_recovery"] == {
        "attempt": 2,
        "recovery_attempted": True,
        "recovery_ok": True,
        "recovery_operation": "init",
        "recovered_after_failure": "driver_unavailable",
        "recovery_elapsed_ms": 12.0,
    }


def test_capture_raw_snapshot_preserves_driver_timeout() -> None:
    xml_dumper = FakeXmlDumper(
        DriverXmlDump.failure(
            backend="fake",
            code="driver_timeout",
            detail="xml timed out",
            device_id="RFCN4010FCK",
            elapsed_ms=1.0,
        )
    )

    result = capture_raw_snapshot(
        xml_dumper=xml_dumper,
        screenshot_capturer=FakeScreenshotCapturer(),
        devices=[DeviceInfo(serial="RFCN4010FCK", state="device")],
        requested_serial="RFCN4010FCK",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_timeout"
