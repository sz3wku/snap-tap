from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter, sleep
from typing import Protocol

from snap_tap.backends.android.uiautomator2.navigation import (
    NAVIGATION_BACK,
    NAVIGATION_HOME,
    NAVIGATION_SWIPE,
    NAVIGATION_UNLOCK,
    NAVIGATION_WAKE,
    SWIPE_DIRECTIONS,
)
from snap_tap.backends.contracts import DriverError, DriverNavigation
from snap_tap.device.identity import normalize_serial
from snap_tap.primitives.lease import PrimitiveLeaseManager, default_lease_manager
from snap_tap.primitives.models import (
    PrimitiveDriverResult,
    PrimitiveLease,
    PrimitiveLeaseConflict,
    PrimitiveNavigationRequest,
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
)
from snap_tap.primitives.navigation_receipt import build_navigation_receipt
from snap_tap.primitives.navigation_request import (
    NAVIGATION_WAIT,
    invalid_navigation_request_detail,
    navigation_request_payload,
    safe_navigation_operation,
)
from snap_tap.primitives.navigation_snapshot import (
    capture_navigation_snapshot,
    exception_detail,
    snapshot_failure_detail,
)
from snap_tap.primitives.proof import (
    settle_after_driver_action,
    status_for_driver_and_proof,
)
from snap_tap.primitives.receipt import invalid_request_receipt, utc_now
from snap_tap.primitives.snapshot_provider import PrimitiveSnapshotProvider
from snap_tap.semantics import SemanticSnapshot


class PrimitiveNavigator(Protocol):
    backend_name: str

    def back(self, *, device_id: str, timeout_s: float = 10.0) -> DriverNavigation: ...

    def home(self, *, device_id: str, timeout_s: float = 10.0) -> DriverNavigation: ...

    def wake(self, *, device_id: str, timeout_s: float = 10.0) -> DriverNavigation: ...

    def unlock(
        self, *, device_id: str, timeout_s: float = 10.0
    ) -> DriverNavigation: ...

    def swipe(
        self,
        *,
        device_id: str,
        direction: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration_ms: int,
        distance_ratio: float,
        timeout_s: float = 10.0,
    ) -> DriverNavigation: ...


@dataclass(frozen=True)
class _SwipeCoordinates:
    x1: float
    y1: float
    x2: float
    y2: float


def navigation_primitive(
    request: PrimitiveNavigationRequest,
    *,
    snapshot_provider: PrimitiveSnapshotProvider,
    navigator: PrimitiveNavigator | None = None,
    lease_manager: PrimitiveLeaseManager | None = None,
) -> PrimitiveReceipt:
    started = perf_counter()
    started_at = utc_now()
    serial = normalize_serial(request.device_id)
    invalid_detail = invalid_navigation_request_detail(request, serial)
    if invalid_detail is not None:
        return invalid_request_receipt(
            device_id=serial,
            request=navigation_request_payload(request),
            detail=invalid_detail,
            operation=safe_navigation_operation(request.operation),
            started_at=started_at,
        )
    assert serial is not None

    manager = lease_manager or default_lease_manager()
    lease: PrimitiveLease | None = None
    try:
        lease = manager.acquire(
            device_id=serial,
            holder_kind="primitive",
            timeout_s=request.lease_timeout_s,
        )
        before = (
            capture_navigation_snapshot(
                snapshot_provider,
                device_id=serial,
                timeout_s=request.timeout_s,
                failure_code="primitive_snapshot_blocked",
                started=started,
            )
            if _requires_before_snapshot(request.operation)
            else None
        )
        if before is not None and (not before.ok or before.snapshot is None):
            return _receipt(
                started=started,
                started_at=started_at,
                device_id=serial,
                lease=lease,
                request=request,
                status="blocked",
                before=before,
                fresh=before,
                driver=None,
                after=None,
                blocking_code="primitive_snapshot_blocked",
                blocking_detail=snapshot_failure_detail(before),
                error=DriverError(
                    code="primitive_snapshot_blocked",
                    detail=snapshot_failure_detail(before),
                ),
            )

        if request.operation == NAVIGATION_WAIT:
            assert before is not None
            return _wait_receipt(
                started=started,
                started_at=started_at,
                device_id=serial,
                lease=lease,
                request=request,
                before=before,
                snapshot_provider=snapshot_provider,
            )

        driver = _run_navigation_driver(
            request,
            device_id=serial,
            before_snapshot=before.snapshot if before is not None else None,
            navigator=navigator,
            started=started,
        )
        if isinstance(driver, DriverError):
            return _receipt(
                started=started,
                started_at=started_at,
                device_id=serial,
                lease=lease,
                request=request,
                status="blocked",
                before=before,
                fresh=before,
                driver=None,
                after=None,
                blocking_code=driver.code,
                blocking_detail=driver.detail,
                error=driver,
            )
        settle_after_driver_action(
            driver,
            settle_ms=request.post_action_settle_ms,
        )
        after = (
            capture_navigation_snapshot(
                snapshot_provider,
                device_id=serial,
                timeout_s=request.timeout_s,
                failure_code="primitive_after_snapshot_failed",
                started=started,
            )
            if driver.attempted or driver.confirmed
            else None
        )
        status, error = status_for_driver_and_proof(
            driver,
            after,
            proof_required=False,
        )
        return _receipt(
            started=started,
            started_at=started_at,
            device_id=serial,
            lease=lease,
            request=request,
            status=status,
            before=before,
            fresh=before,
            driver=driver,
            after=after,
            error=error,
        )
    except PrimitiveLeaseConflict as exc:
        return _receipt(
            started=started,
            started_at=started_at,
            device_id=serial,
            lease=exc.lease,
            request=request,
            status="blocked",
            before=None,
            fresh=None,
            driver=None,
            after=None,
            blocking_code="primitive_lease_conflict",
            blocking_detail=exc.detail,
            error=DriverError(code="primitive_lease_conflict", detail=exc.detail),
        )
    finally:
        if lease is not None:
            manager.release(lease)


def _wait_receipt(
    *,
    started: float,
    started_at: str,
    device_id: str,
    lease: PrimitiveLease,
    request: PrimitiveNavigationRequest,
    before: PrimitiveSnapshotResult,
    snapshot_provider: PrimitiveSnapshotProvider,
) -> PrimitiveReceipt:
    sleep(request.seconds)
    after = capture_navigation_snapshot(
        snapshot_provider,
        device_id=device_id,
        timeout_s=request.timeout_s,
        failure_code="primitive_after_snapshot_failed",
        started=started,
    )
    status = "completed" if after.ok and after.snapshot is not None else "partial"
    error = None
    if status != "completed":
        error = DriverError(
            code="primitive_after_snapshot_failed",
            detail=snapshot_failure_detail(after),
        )
    return _receipt(
        started=started,
        started_at=started_at,
        device_id=device_id,
        lease=lease,
        request=request,
        status=status,
        before=before,
        fresh=before,
        driver=None,
        after=after,
        error=error,
    )


def _run_navigation_driver(
    request: PrimitiveNavigationRequest,
    *,
    device_id: str,
    before_snapshot: SemanticSnapshot | None,
    navigator: PrimitiveNavigator | None,
    started: float,
) -> PrimitiveDriverResult | DriverError:
    if navigator is None:
        from snap_tap.backends.android.uiautomator2.navigation import (
            Uiautomator2Navigator,
        )

        navigator = Uiautomator2Navigator()
    try:
        if request.operation == NAVIGATION_BACK:
            return _primitive_driver_result(
                navigator.back(device_id=device_id, timeout_s=request.timeout_s)
            )
        if request.operation == NAVIGATION_HOME:
            return _primitive_driver_result(
                navigator.home(device_id=device_id, timeout_s=request.timeout_s)
            )
        if request.operation == NAVIGATION_WAKE:
            return _primitive_driver_result(
                navigator.wake(device_id=device_id, timeout_s=request.timeout_s)
            )
        if request.operation == NAVIGATION_UNLOCK:
            return _primitive_driver_result(
                navigator.unlock(device_id=device_id, timeout_s=request.timeout_s)
            )
        if before_snapshot is None:
            return DriverError(
                code="primitive_viewport_blocked",
                detail="Swipe requires a fresh viewport snapshot.",
            )
        coords = _swipe_coordinates(before_snapshot, request)
        if isinstance(coords, DriverError):
            return coords
        return _primitive_driver_result(
            navigator.swipe(
                device_id=device_id,
                direction=request.direction or "",
                x1=coords.x1,
                y1=coords.y1,
                x2=coords.x2,
                y2=coords.y2,
                duration_ms=request.duration_ms,
                distance_ratio=request.distance_ratio,
                timeout_s=request.timeout_s,
            )
        )
    except Exception as exc:
        return PrimitiveDriverResult(
            ok=False,
            backend=getattr(navigator, "backend_name", "unknown"),
            operation=request.operation,
            elapsed_ms=round((perf_counter() - started) * 1000, 3),
            attempted=True,
            confirmed=False,
            checked_at=utc_now(),
            metadata={"touch_may_have_occurred": True},
            error=DriverError(
                code="primitive_driver_failed",
                detail=exception_detail(exc),
            ),
        )


def _swipe_coordinates(
    snapshot: SemanticSnapshot,
    request: PrimitiveNavigationRequest,
) -> _SwipeCoordinates | DriverError:
    viewport = snapshot.screen_metadata.viewport
    width = viewport.width
    height = viewport.height
    if width is None or height is None or width <= 0 or height <= 0:
        return DriverError(
            code="primitive_viewport_blocked",
            detail="Swipe requires a positive viewport width and height.",
        )
    direction = request.direction
    assert direction in SWIPE_DIRECTIONS
    if direction in {"up", "down"}:
        distance = min(height * request.distance_ratio, height * 0.80)
        x = width / 2
        start_y = (
            (height + distance) / 2 if direction == "up" else (height - distance) / 2
        )
        end_y = (
            (height - distance) / 2 if direction == "up" else (height + distance) / 2
        )
        return _SwipeCoordinates(x, start_y, x, end_y)
    distance = min(width * request.distance_ratio, width * 0.80)
    y = height / 2
    start_x = (width + distance) / 2 if direction == "left" else (width - distance) / 2
    end_x = (width - distance) / 2 if direction == "left" else (width + distance) / 2
    return _SwipeCoordinates(start_x, y, end_x, y)


def _primitive_driver_result(result: DriverNavigation) -> PrimitiveDriverResult:
    return PrimitiveDriverResult(
        ok=result.ok,
        backend=result.backend,
        operation=result.operation,
        elapsed_ms=result.elapsed_ms,
        attempted=result.attempted,
        confirmed=result.confirmed,
        checked_at=result.checked_at,
        metadata=dict(result.metadata),
        error=result.error,
    )


def _receipt(
    *,
    started: float,
    started_at: str,
    device_id: str,
    lease: PrimitiveLease | None,
    request: PrimitiveNavigationRequest,
    status: str,
    before: PrimitiveSnapshotResult | None,
    fresh: PrimitiveSnapshotResult | None,
    driver: PrimitiveDriverResult | None,
    after: PrimitiveSnapshotResult | None,
    blocking_code: str | None = None,
    blocking_detail: str | None = None,
    error: DriverError | None = None,
) -> PrimitiveReceipt:
    return build_navigation_receipt(
        elapsed_ms=round((perf_counter() - started) * 1000, 3),
        started_at=started_at,
        finished_at=utc_now(),
        status=status,
        device_id=device_id,
        lease=lease,
        request=request,
        before=before,
        fresh=fresh,
        driver=driver,
        after=after,
        blocking_code=blocking_code,
        blocking_detail=blocking_detail,
        error=error,
    )


def _requires_before_snapshot(operation: str) -> bool:
    return operation in {NAVIGATION_SWIPE, NAVIGATION_WAIT}
