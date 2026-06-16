from __future__ import annotations

from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.contracts import (
    DriverScreenshot,
    capture_device_screenshot,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"


class FakeScreenshotCapturer:
    backend_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []

    def capture(
        self,
        device_id: str,
        timeout_s: float = 10.0,
    ) -> DriverScreenshot:
        self.calls.append((device_id, timeout_s))
        return DriverScreenshot.success(
            device_id=device_id,
            backend=self.backend_name,
            elapsed_ms=1.0,
            image_bytes=PNG_BYTES,
            metadata={
                "format": "png",
                "width": 1080,
                "height": 2400,
                "byte_length": len(PNG_BYTES),
                "sha256": "fake",
                "timeout_s": timeout_s,
            },
        )


def test_capture_device_screenshot_blocks_ambiguous_multi_device_selection() -> None:
    capturer = FakeScreenshotCapturer()

    result = capture_device_screenshot(
        capturer=capturer,
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
    assert capturer.calls == []


def test_capture_device_screenshot_blocks_when_no_devices_are_visible() -> None:
    capturer = FakeScreenshotCapturer()

    result = capture_device_screenshot(
        capturer=capturer,
        devices=[],
        requested_serial=None,
    )

    assert result.ok is False
    assert result.status == "blocked"
    assert result.error is not None
    assert result.error.code == "device_offline"
    assert capturer.calls == []


def test_capture_device_screenshot_calls_capturer_for_explicit_serial() -> None:
    capturer = FakeScreenshotCapturer()

    result = capture_device_screenshot(
        capturer=capturer,
        devices=[
            DeviceInfo(serial="RFCN4010FCK", state="device"),
            DeviceInfo(serial="R58R502HMSJ", state="device"),
        ],
        requested_serial="RFCN4010FCK",
        timeout_s=3.0,
    )

    assert result.ok is True
    assert result.operation == "screenshot"
    assert result.image_bytes == PNG_BYTES
    assert capturer.calls == [("RFCN4010FCK", 3.0)]
