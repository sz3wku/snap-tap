from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Protocol

from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.contracts import DriverError
from snap_tap.backends.contracts import DriverScreenshotCapturer
from snap_tap.backends.contracts import DriverXmlDumper
from snap_tap.primitives.models import PrimitiveSnapshotResult
from snap_tap.semantics import SemanticSnapshotError, build_semantic_snapshot
from snap_tap.snapshots import capture_raw_snapshot, materialize_raw_snapshot_artifacts


DEFAULT_PRIMITIVE_SNAPSHOT_ROOT = Path("temp/mobile-primitives")


class PrimitiveSnapshotProvider(Protocol):
    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        ...


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
