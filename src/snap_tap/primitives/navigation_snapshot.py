from __future__ import annotations

from time import perf_counter

from snap_tap.backends.contracts import DriverError
from snap_tap.primitives.models import PrimitiveSnapshotResult
from snap_tap.primitives.receipt import utc_now
from snap_tap.primitives.snapshot_provider import PrimitiveSnapshotProvider


def capture_navigation_snapshot(
    provider: PrimitiveSnapshotProvider,
    *,
    device_id: str,
    timeout_s: float,
    failure_code: str,
    started: float,
) -> PrimitiveSnapshotResult:
    try:
        return provider.capture(device_id, timeout_s=timeout_s)
    except Exception as exc:
        return PrimitiveSnapshotResult(
            ok=False,
            status="failed",
            device_id=device_id,
            checked_at=utc_now(),
            elapsed_ms=round((perf_counter() - started) * 1000, 3),
            error=DriverError(code=failure_code, detail=exception_detail(exc)),
        )


def snapshot_failure_detail(snapshot: PrimitiveSnapshotResult | None) -> str:
    if snapshot is not None and snapshot.error is not None:
        return snapshot.error.detail
    return "Primitive snapshot capture failed."


def exception_detail(exc: Exception) -> str:
    detail = f"{type(exc).__name__}: {exc}".strip()
    if len(detail) > 300:
        return "Primitive operation failed with oversized error detail."
    return detail
