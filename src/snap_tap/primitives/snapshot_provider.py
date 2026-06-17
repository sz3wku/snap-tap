from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Protocol

from snap_tap.backends.contracts import (
    DriverError,
    DriverScreenshotCapturer,
    DriverXmlDump,
    DriverXmlDumper,
)
from snap_tap.device.identity import DeviceInfo
from snap_tap.primitives.models import PrimitiveSnapshotResult
from snap_tap.semantics import SemanticSnapshotError, build_semantic_snapshot
from snap_tap.snapshots import (
    RawSnapshotCapture,
    capture_raw_observation,
    capture_raw_snapshot,
    complete_operator_observation,
    materialize_raw_snapshot_artifacts,
)

DEFAULT_PRIMITIVE_SNAPSHOT_ROOT = Path("temp/mobile-primitives")
_PRESERVE_DRIVER_CODES = {
    "device_offline",
    "driver_conflict",
    "driver_timeout",
    "driver_unavailable",
}


class PrimitiveSnapshotProvider(Protocol):
    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        ...


class CorePrimitiveObservationProvider:
    def __init__(
        self,
        *,
        devices: Sequence[DeviceInfo],
        xml_dumper: DriverXmlDumper,
    ) -> None:
        self._devices = tuple(devices)
        self._xml_dumper = xml_dumper

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        started = perf_counter()
        raw = capture_raw_observation(
            xml_dumper=self._xml_dumper,
            devices=self._devices,
            requested_serial=device_id,
            timeout_s=timeout_s,
        )
        if raw.ok:
            raw = complete_operator_observation(raw)
        return _result_from_raw(raw, started=started)

    def complete_xml_dump(
        self,
        xml_dump: DriverXmlDump,
        *,
        timeout_s: float = 10.0,
    ) -> PrimitiveSnapshotResult:
        started = perf_counter()
        raw = _raw_observation_from_xml_dump(xml_dump, timeout_s=timeout_s)
        if raw.ok:
            raw = complete_operator_observation(raw)
        return _result_from_raw(raw, started=started)


class CorePrimitiveSnapshotProvider:
    def __init__(
        self,
        *,
        devices: Sequence[DeviceInfo],
        xml_dumper: DriverXmlDumper,
        screenshot_capturer: DriverScreenshotCapturer,
        artifact_root: Path = DEFAULT_PRIMITIVE_SNAPSHOT_ROOT,
    ) -> None:
        self._devices = tuple(devices)
        self._xml_dumper = xml_dumper
        self._screenshot_capturer = screenshot_capturer
        self._artifact_root = artifact_root

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        started = perf_counter()
        raw = capture_raw_snapshot(
            xml_dumper=self._xml_dumper,
            screenshot_capturer=self._screenshot_capturer,
            devices=self._devices,
            requested_serial=device_id,
            timeout_s=timeout_s,
        )
        if raw.ok:
            raw = materialize_raw_snapshot_artifacts(raw, self._artifact_root)
        return _result_from_raw(raw, started=started)


def _result_from_raw(
    raw: RawSnapshotCapture,
    *,
    started: float,
) -> PrimitiveSnapshotResult:
    if not raw.ok:
        return PrimitiveSnapshotResult(
            ok=False,
            status=raw.status,
            device_id=raw.device_id,
            checked_at=raw.checked_at,
            elapsed_ms=raw.elapsed_ms,
            backend=raw.backend,
            error=raw.error,
        )
    try:
        snapshot = build_semantic_snapshot(raw)
    except SemanticSnapshotError as exc:
        return PrimitiveSnapshotResult(
            ok=False,
            status="blocked",
            device_id=raw.device_id,
            checked_at=raw.checked_at,
            elapsed_ms=round((perf_counter() - started) * 1000, 3),
            backend=raw.backend,
            error=DriverError(code=exc.code, detail=exc.detail),
        )
    return PrimitiveSnapshotResult(
        ok=True,
        status="completed",
        device_id=snapshot.device_id,
        checked_at=snapshot.captured_at,
        elapsed_ms=round((perf_counter() - started) * 1000, 3),
        snapshot=snapshot,
        backend=raw.backend,
    )


def _raw_observation_from_xml_dump(
    xml_dump: DriverXmlDump,
    *,
    timeout_s: float,
) -> RawSnapshotCapture:
    if not xml_dump.ok:
        source_code = xml_dump.error.code if xml_dump.error is not None else "dump_failed"
        return RawSnapshotCapture.failure(
            backend=xml_dump.backend,
            code=_snapshot_xml_error_code(source_code),
            detail=_source_detail(xml_dump.error, "Operator observation XML failed."),
            device_id=xml_dump.device_id,
            elapsed_ms=xml_dump.elapsed_ms,
            metadata={
                "source_elapsed_ms": xml_dump.elapsed_ms,
                "source_error_code": source_code,
                "stage": "xml",
                "timeout_s": timeout_s,
            },
        )
    xml = xml_dump.xml
    if not isinstance(xml, str) or not xml.strip():
        return RawSnapshotCapture.failure(
            backend=xml_dump.backend,
            code="snapshot_dump_failed",
            detail="Operator observation completed without XML content.",
            device_id=xml_dump.device_id,
            elapsed_ms=xml_dump.elapsed_ms,
            metadata={
                "source_elapsed_ms": xml_dump.elapsed_ms,
                "stage": "xml",
                "timeout_s": timeout_s,
            },
        )
    return RawSnapshotCapture.observation_success(
        device_id=xml_dump.device_id or "",
        backend=xml_dump.backend,
        elapsed_ms=xml_dump.elapsed_ms,
        xml=xml,
        metadata={
            "timeout_s": timeout_s,
            "xml_elapsed_ms": xml_dump.elapsed_ms,
        },
    )


def _snapshot_xml_error_code(source_code: str) -> str:
    if source_code in _PRESERVE_DRIVER_CODES:
        return source_code
    return "snapshot_dump_failed"


def _source_detail(error: DriverError | None, fallback: str) -> str:
    if error is None:
        return fallback
    if error.code not in _PRESERVE_DRIVER_CODES:
        return fallback
    if _contains_sensitive_detail(error.detail):
        return fallback
    return error.detail


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
