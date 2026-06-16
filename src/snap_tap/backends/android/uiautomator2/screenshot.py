from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
import hashlib
import sys
from time import perf_counter

from snap_tap.device.identity import normalize_serial
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
from snap_tap.backends.contracts import DriverScreenshot


class Uiautomator2ScreenshotCapturer:
    backend_name = "uiautomator2"

    def __init__(
        self,
        *,
        process_runner: ProcessRunner | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._process_runner = process_runner or SubprocessRunner()
        self._python_executable = python_executable or sys.executable

    def capture(
        self,
        device_id: str,
        timeout_s: float = 10.0,
    ) -> DriverScreenshot:
        return capture_uiautomator2_screenshot(
            device_id=device_id,
            timeout_s=timeout_s,
            process_runner=self._process_runner,
            python_executable=self._python_executable,
        )


def capture_uiautomator2_screenshot(
    *,
    device_id: str,
    timeout_s: float = 10.0,
    process_runner: ProcessRunner | None = None,
    python_executable: str | None = None,
) -> DriverScreenshot:
    started = perf_counter()
    serial = normalize_serial(device_id)
    runner = process_runner or SubprocessRunner()
    executable = python_executable or sys.executable

    if serial is None:
        return DriverScreenshot.failure(
            backend="uiautomator2",
            code="device_offline",
            detail="Device serial is required and must be a valid ADB serial.",
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
            metadata={"timeout_s": timeout_s},
        )

    result = _capture_uiautomator2_screenshot_once(
        serial=serial,
        timeout_s=timeout_s,
        runner=runner,
        executable=executable,
        started=started,
    )
    return retry_once_after_recovery(
        result,
        device_id=serial,
        operation="screenshot",
        process_runner=runner,
        python_executable=executable,
        retry=lambda: _capture_uiautomator2_screenshot_once(
            serial=serial,
            timeout_s=timeout_s,
            runner=runner,
            executable=executable,
            started=started,
        ),
    )


def _capture_uiautomator2_screenshot_once(
    *,
    serial: str,
    timeout_s: float,
    runner: ProcessRunner,
    executable: str,
    started: float,
) -> DriverScreenshot:
    args = [
        executable,
        "-m",
        "snap_tap.backends.android.uiautomator2.probes",
        "screenshot",
        "--device",
        serial,
    ]
    try:
        result = runner.run(args, timeout_s=timeout_s)
    except ProcessTimeoutError as exc:
        return DriverScreenshot.failure(
            backend="uiautomator2",
            code="driver_timeout",
            detail=str(exc) or "uiautomator2 screenshot timed out.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": timeout_s},
        )
    except OSError as exc:
        return DriverScreenshot.failure(
            backend="uiautomator2",
            code="driver_unavailable",
            detail=str(exc) or "uiautomator2 screenshot driver is unavailable.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata={"timeout_s": timeout_s},
        )

    payload = parse_probe_payload(result.stdout)
    metadata = _probe_metadata(payload, timeout_s=timeout_s)
    if result.returncode != 0 or payload.get("ok") is not True:
        return DriverScreenshot.failure(
            backend="uiautomator2",
            code=_probe_error_code(payload),
            detail=_probe_error_detail(payload),
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
        )

    image_bytes = _decode_image(payload.get("image_base64"))
    if image_bytes is None:
        return DriverScreenshot.failure(
            backend="uiautomator2",
            code="screenshot_failed",
            detail="uiautomator2 screenshot probe returned invalid image bytes.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
        )
    if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return DriverScreenshot.failure(
            backend="uiautomator2",
            code="screenshot_failed",
            detail="uiautomator2 screenshot probe returned a non-PNG payload.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
        )

    image_metadata = _image_metadata(image_bytes, metadata, timeout_s=timeout_s)
    if image_metadata is None:
        return DriverScreenshot.failure(
            backend="uiautomator2",
            code="screenshot_failed",
            detail="uiautomator2 screenshot probe returned invalid metadata.",
            device_id=serial,
            elapsed_ms=_elapsed_ms(started),
            metadata=metadata,
        )

    return DriverScreenshot.success(
        device_id=serial,
        backend="uiautomator2",
        elapsed_ms=_elapsed_ms(started),
        image_bytes=image_bytes,
        metadata=image_metadata,
    )


def _probe_metadata(
    payload: Mapping[str, object],
    *,
    timeout_s: float,
) -> dict[str, object]:
    metadata: dict[str, object] = {"timeout_s": timeout_s}
    raw_metadata = payload.get("metadata")
    if not isinstance(raw_metadata, Mapping):
        return metadata
    image_format = raw_metadata.get("format")
    if isinstance(image_format, str):
        metadata["format"] = image_format.lower()
    width = _positive_int(raw_metadata.get("width"))
    if width is not None:
        metadata["width"] = width
    height = _positive_int(raw_metadata.get("height"))
    if height is not None:
        metadata["height"] = height
    return metadata


def _decode_image(raw_image: object) -> bytes | None:
    if not isinstance(raw_image, str) or not raw_image.strip():
        return None
    try:
        image_bytes = base64.b64decode(raw_image, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not image_bytes:
        return None
    return image_bytes


def _image_metadata(
    image_bytes: bytes,
    metadata: Mapping[str, object],
    *,
    timeout_s: float,
) -> dict[str, object] | None:
    width = _positive_int(metadata.get("width"))
    height = _positive_int(metadata.get("height"))
    image_format = str(metadata.get("format", "")).lower()
    if width is None or height is None or image_format != "png":
        return None
    return {
        "format": "png",
        "width": width,
        "height": height,
        "byte_length": len(image_bytes),
        "sha256": hashlib.sha256(image_bytes).hexdigest(),
        "timeout_s": timeout_s,
    }


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        candidate = value
    elif isinstance(value, str):
        try:
            candidate = int(value)
        except ValueError:
            return None
    else:
        return None
    if candidate <= 0:
        return None
    return candidate


def _probe_error_code(payload: Mapping[str, object]) -> str:
    return probe_error_code(payload, default_code="screenshot_failed")


def _probe_error_detail(payload: Mapping[str, object]) -> str:
    return probe_error_detail(
        payload,
        operation="screenshot",
        sensitive_markers=("image_base64", "image_bytes", "data:image", "ivbor"),
    )


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
