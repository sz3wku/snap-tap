from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter

from snap_tap.backends.contracts import (
    DriverError,
    DriverScreenshot,
    DriverScreenshotCapturer,
    DriverXmlDump,
    DriverXmlDumper,
)
from snap_tap.device.identity import DeviceInfo, select_device
from snap_tap.snapshots.models import RawSnapshotCapture

_PRESERVE_DRIVER_CODES = {
    "device_offline",
    "driver_conflict",
    "driver_timeout",
    "driver_unavailable",
}


def capture_raw_snapshot(
    *,
    xml_dumper: DriverXmlDumper,
    screenshot_capturer: DriverScreenshotCapturer,
    devices: Sequence[DeviceInfo],
    requested_serial: str | None,
    timeout_s: float = 10.0,
) -> RawSnapshotCapture:
    started = perf_counter()
    backend = _combined_backend(
        xml_dumper.backend_name,
        screenshot_capturer.backend_name,
    )
    if requested_serial is None:
        return RawSnapshotCapture.failure(
            backend=backend,
            code="device_required",
            detail="Snapshot capture requires an explicit device serial.",
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
            metadata={"timeout_s": timeout_s},
        )

    selection = select_device(devices, requested_serial)
    if not selection.ok:
        return RawSnapshotCapture.failure(
            backend=backend,
            code=selection.error_code or "driver_unavailable",
            detail=selection.error_detail or "Device selection failed.",
            device_id=selection.device.serial if selection.device else requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
            metadata={"timeout_s": timeout_s},
        )
    if selection.device is None:
        return RawSnapshotCapture.failure(
            backend=backend,
            code="driver_unavailable",
            detail="Device selection succeeded without a device.",
            device_id=requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
            metadata={"timeout_s": timeout_s},
        )

    device_id = selection.device.serial
    xml_result = xml_dumper.dump_xml(device_id, timeout_s=timeout_s)
    if not xml_result.ok:
        return _xml_failure(xml_result, started=started, timeout_s=timeout_s)
    xml = xml_result.xml
    if not isinstance(xml, str) or not xml.strip():
        return RawSnapshotCapture.failure(
            backend=xml_result.backend,
            code="snapshot_dump_failed",
            detail="Snapshot XML capture completed without XML content.",
            device_id=device_id,
            elapsed_ms=_elapsed_ms(started),
            metadata=_failure_metadata(
                stage="xml",
                timeout_s=timeout_s,
                source_elapsed_ms=xml_result.elapsed_ms,
            ),
        )

    screenshot_result = screenshot_capturer.capture(device_id, timeout_s=timeout_s)
    if not screenshot_result.ok:
        return _screenshot_failure(
            screenshot_result,
            xml_result=xml_result,
            started=started,
            timeout_s=timeout_s,
        )
    image_bytes = screenshot_result.image_bytes
    if image_bytes is None:
        return RawSnapshotCapture.failure(
            backend=screenshot_result.backend,
            code="snapshot_evidence_missing",
            detail="Snapshot screenshot capture completed without image bytes.",
            device_id=device_id,
            elapsed_ms=_elapsed_ms(started),
            metadata=_failure_metadata(
                stage="screenshot",
                timeout_s=timeout_s,
                source_elapsed_ms=screenshot_result.elapsed_ms,
                prior_metadata=xml_result.metadata,
            ),
        )

    return RawSnapshotCapture.success(
        device_id=device_id,
        backend=_combined_backend(xml_result.backend, screenshot_result.backend),
        elapsed_ms=_elapsed_ms(started),
        xml=xml,
        image_bytes=image_bytes,
        metadata=_success_metadata(
            xml_result=xml_result,
            screenshot_result=screenshot_result,
            timeout_s=timeout_s,
        ),
    )


def capture_raw_observation(
    *,
    xml_dumper: DriverXmlDumper,
    devices: Sequence[DeviceInfo],
    requested_serial: str | None,
    timeout_s: float = 10.0,
) -> RawSnapshotCapture:
    started = perf_counter()
    backend = xml_dumper.backend_name
    if requested_serial is None:
        return RawSnapshotCapture.failure(
            backend=backend,
            code="device_required",
            detail="Operator observation requires an explicit device serial.",
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
            metadata={"timeout_s": timeout_s},
        )

    selection = select_device(devices, requested_serial)
    if not selection.ok:
        return RawSnapshotCapture.failure(
            backend=backend,
            code=selection.error_code or "driver_unavailable",
            detail=selection.error_detail or "Device selection failed.",
            device_id=selection.device.serial if selection.device else requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
            metadata={"timeout_s": timeout_s},
        )
    if selection.device is None:
        return RawSnapshotCapture.failure(
            backend=backend,
            code="driver_unavailable",
            detail="Device selection succeeded without a device.",
            device_id=requested_serial,
            elapsed_ms=_elapsed_ms(started),
            status="blocked",
            metadata={"timeout_s": timeout_s},
        )

    device_id = selection.device.serial
    xml_result = xml_dumper.dump_xml(device_id, timeout_s=timeout_s)
    if not xml_result.ok:
        return _xml_failure(xml_result, started=started, timeout_s=timeout_s)
    xml = xml_result.xml
    if not isinstance(xml, str) or not xml.strip():
        return RawSnapshotCapture.failure(
            backend=xml_result.backend,
            code="snapshot_dump_failed",
            detail="Operator observation completed without XML content.",
            device_id=device_id,
            elapsed_ms=_elapsed_ms(started),
            metadata=_failure_metadata(
                stage="xml",
                timeout_s=timeout_s,
                source_elapsed_ms=xml_result.elapsed_ms,
            ),
        )

    return RawSnapshotCapture.observation_success(
        device_id=device_id,
        backend=xml_result.backend,
        elapsed_ms=_elapsed_ms(started),
        xml=xml,
        metadata=_observation_success_metadata(
            xml_result=xml_result,
            timeout_s=timeout_s,
        ),
    )


def _success_metadata(
    *,
    xml_result: DriverXmlDump,
    screenshot_result: DriverScreenshot,
    timeout_s: float,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "timeout_s": timeout_s,
        "xml_elapsed_ms": xml_result.elapsed_ms,
        "screenshot_elapsed_ms": screenshot_result.elapsed_ms,
        "screenshot_format": screenshot_result.metadata.get("format"),
        "screenshot_width": screenshot_result.metadata.get("width"),
        "screenshot_height": screenshot_result.metadata.get("height"),
    }
    xml_recovery = _recovery_metadata(xml_result.metadata)
    if xml_recovery is not None:
        metadata["xml_recovery"] = xml_recovery
    screenshot_recovery = _recovery_metadata(screenshot_result.metadata)
    if screenshot_recovery is not None:
        metadata["screenshot_recovery"] = screenshot_recovery
    return metadata


def _observation_success_metadata(
    *,
    xml_result: DriverXmlDump,
    timeout_s: float,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "timeout_s": timeout_s,
        "xml_elapsed_ms": xml_result.elapsed_ms,
    }
    for source_key, target_key in (
        ("displayWidth", "viewport_width"),
        ("displayHeight", "viewport_height"),
    ):
        value = _positive_int_metadata(xml_result.metadata.get(source_key))
        if value is not None:
            metadata[target_key] = value
    xml_recovery = _recovery_metadata(xml_result.metadata)
    if xml_recovery is not None:
        metadata["xml_recovery"] = xml_recovery
    return metadata


def _xml_failure(
    result: DriverXmlDump,
    *,
    started: float,
    timeout_s: float,
) -> RawSnapshotCapture:
    source_code = result.error.code if result.error is not None else "dump_failed"
    return RawSnapshotCapture.failure(
        backend=result.backend,
        code=_snapshot_xml_error_code(source_code),
        detail=_source_detail(result.error, "Snapshot XML capture failed."),
        device_id=result.device_id,
        elapsed_ms=_elapsed_ms(started),
        metadata=_failure_metadata(
            stage="xml",
            timeout_s=timeout_s,
            source_error_code=source_code,
            source_elapsed_ms=result.elapsed_ms,
            source_metadata=result.metadata,
        ),
    )


def _screenshot_failure(
    result: DriverScreenshot,
    *,
    xml_result: DriverXmlDump,
    started: float,
    timeout_s: float,
) -> RawSnapshotCapture:
    source_code = (
        result.error.code if result.error is not None else "screenshot_failed"
    )
    return RawSnapshotCapture.failure(
        backend=result.backend,
        code=_snapshot_screenshot_error_code(source_code),
        detail=_source_detail(result.error, "Snapshot screenshot capture failed."),
        device_id=result.device_id,
        elapsed_ms=_elapsed_ms(started),
        metadata=_failure_metadata(
            stage="screenshot",
            timeout_s=timeout_s,
            source_error_code=source_code,
            source_elapsed_ms=result.elapsed_ms,
            source_metadata=result.metadata,
            prior_metadata=xml_result.metadata,
        ),
    )


def _snapshot_xml_error_code(source_code: str) -> str:
    if source_code in _PRESERVE_DRIVER_CODES:
        return source_code
    return "snapshot_dump_failed"


def _snapshot_screenshot_error_code(source_code: str) -> str:
    if source_code in _PRESERVE_DRIVER_CODES:
        return source_code
    return "snapshot_evidence_missing"


def _source_detail(error: DriverError | None, fallback: str) -> str:
    if error is None:
        return fallback
    if error.code not in _PRESERVE_DRIVER_CODES:
        return fallback
    if _contains_sensitive_detail(error.detail):
        return fallback
    return error.detail


def _failure_metadata(
    *,
    stage: str,
    timeout_s: float,
    source_error_code: str | None = None,
    source_elapsed_ms: float | None = None,
    source_metadata: Mapping[str, object] | None = None,
    prior_metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {"stage": stage, "timeout_s": timeout_s}
    if source_error_code is not None:
        metadata["source_error_code"] = source_error_code
    if source_elapsed_ms is not None:
        metadata["source_elapsed_ms"] = source_elapsed_ms
    if source_metadata is not None:
        recovery = _recovery_metadata(source_metadata)
        if recovery is not None:
            metadata[f"{stage}_recovery"] = recovery
    if stage == "screenshot" and prior_metadata is not None:
        xml_recovery = _recovery_metadata(prior_metadata)
        if xml_recovery is not None:
            metadata["xml_recovery"] = xml_recovery
    return metadata


def _recovery_metadata(metadata: Mapping[str, object]) -> dict[str, object] | None:
    if metadata.get("recovery_attempted") is not True:
        return None
    public: dict[str, object] = {"recovery_attempted": True}
    attempt = metadata.get("attempt")
    if isinstance(attempt, int) and not isinstance(attempt, bool):
        public["attempt"] = attempt
    recovery_ok = metadata.get("recovery_ok")
    if isinstance(recovery_ok, bool):
        public["recovery_ok"] = recovery_ok
    for key in (
        "recovery_operation",
        "recovered_after_failure",
        "recovery_error_code",
    ):
        value = metadata.get(key)
        if isinstance(value, str):
            public[key] = value
    recovery_elapsed_ms = metadata.get("recovery_elapsed_ms")
    if isinstance(recovery_elapsed_ms, (int, float)) and not isinstance(
        recovery_elapsed_ms,
        bool,
    ):
        public["recovery_elapsed_ms"] = recovery_elapsed_ms
    return public


def _contains_sensitive_detail(detail: str) -> bool:
    lowered = detail.lower()
    markers = (
        "<hierarchy",
        "<node",
        "image_base64",
        "image_bytes",
        "data:image",
        "base64",
        "ivbor",
    )
    return any(marker in lowered for marker in markers)


def _positive_int_metadata(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def _combined_backend(first: str, second: str) -> str:
    if first == second:
        return first
    return f"{first}+{second}"


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
